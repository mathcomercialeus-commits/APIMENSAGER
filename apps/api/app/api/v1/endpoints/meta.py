from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor, request_ip
from app.core.database import get_db_session
from app.core.security import verify_meta_signature
from app.models.crm import Conversation, ConversationMessage, WhatsAppChannel
from app.models.enums import (
    ConversationEventType,
    MessageDeliveryStatus,
    MessageDirection,
    MessageSenderType,
    MessageType,
)
from app.models.meta import ChannelCredential, MessageTemplate, WebhookEvent
from app.schemas.meta import (
    ChannelCredentialRead,
    ChannelCredentialUpsert,
    MessageTemplateRead,
    OutboundMessageResponse,
    SendTemplateMessageRequest,
    SendTextMessageRequest,
    TemplatesSyncResponse,
    WebhookAck,
)
from app.services.access import CurrentActor
from app.services.audit import record_audit_log
from app.services.crm import append_conversation_event, conversation_detail_query_options, touch_conversation_after_message
from app.services.meta_whatsapp import (
    MetaAPIConfigurationError,
    MetaAPIRequestError,
    WhatsAppCloudAPIClient,
    extract_phone_number_id,
    get_app_secret,
    get_channel_credential,
    get_credential_by_phone_number_id,
    get_verify_token,
    is_customer_service_window_open,
    process_incoming_webhook_event,
    set_credential_secrets,
    to_whatsapp_recipient,
)
from app.workers.tasks import enqueue_automation_execution, enqueue_meta_webhook_event


router = APIRouter()


async def _load_channel(session: AsyncSession, channel_id: UUID) -> WhatsAppChannel | None:
    return await session.scalar(select(WhatsAppChannel).where(WhatsAppChannel.id == channel_id))


async def _load_conversation_for_meta(session: AsyncSession, conversation_id: UUID) -> Conversation | None:
    return await session.scalar(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(
            *conversation_detail_query_options(),
        )
    )


def _serialize_credential(credential: ChannelCredential) -> ChannelCredentialRead:
    return ChannelCredentialRead(
        id=credential.id,
        channel_id=credential.channel_id,
        phone_number_id=credential.channel.external_phone_number_id or "",
        app_id=credential.app_id,
        business_account_id=credential.business_account_id,
        graph_api_version=credential.graph_api_version,
        webhook_callback_url=credential.webhook_callback_url,
        verify_token_hint=credential.verify_token_hint,
        access_token_last4=credential.access_token_last4,
        has_access_token=bool(credential.encrypted_access_token),
        has_app_secret=bool(credential.encrypted_app_secret or get_app_secret(None)),
        has_webhook_verify_token=bool(credential.encrypted_webhook_verify_token or get_verify_token(None)),
        is_active=credential.is_active,
        status_payload=credential.status_payload,
        last_healthcheck_at=credential.last_healthcheck_at,
        last_error_at=credential.last_error_at,
        created_at=credential.created_at,
        updated_at=credential.updated_at,
    )


def _serialize_template(template: MessageTemplate) -> MessageTemplateRead:
    return MessageTemplateRead(
        id=template.id,
        meta_template_id=template.meta_template_id,
        name=template.name,
        language_code=template.language_code,
        category=template.category,
        status=template.status,
        components_schema=template.components_schema,
        last_synced_at=template.last_synced_at,
    )


def _ensure_company_meta_access(actor: CurrentActor, channel: WhatsAppChannel, *, manage: bool = False) -> None:
    permission = "meta.manage" if manage else "meta.view"
    if not actor.has_permission(permission, company_id=channel.company_id, store_id=channel.store_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para este canal.")


async def _resolve_webhook_credential(
    session: AsyncSession,
    *,
    explicit_channel_id: UUID | None,
    payload: dict,
) -> ChannelCredential | None:
    if explicit_channel_id:
        return await get_channel_credential(session, explicit_channel_id)
    phone_number_id = extract_phone_number_id(payload)
    if not phone_number_id:
        return None
    return await get_credential_by_phone_number_id(session, phone_number_id)


async def _persist_outbound_message(
    session: AsyncSession,
    *,
    conversation: Conversation,
    actor: CurrentActor,
    direction: MessageDirection,
    sender_type: MessageSenderType,
    message_type: MessageType,
    delivery_status: MessageDeliveryStatus,
    body: str,
    provider_message_id: str | None,
    provider_response: dict,
    sent_at: datetime,
) -> ConversationMessage:
    message = ConversationMessage(
        company_id=conversation.company_id,
        store_id=conversation.store_id,
        channel_id=conversation.channel_id,
        conversation_id=conversation.id,
        author_user_id=actor.user.id,
        direction=direction,
        sender_type=sender_type,
        message_type=message_type,
        delivery_status=delivery_status,
        provider_message_id=provider_message_id,
        text_body=body,
        is_human=True,
        metadata_json={"provider_response": provider_response},
        sent_at=sent_at,
    )
    message.conversation = conversation
    message.channel = conversation.channel
    message.author_user = actor.user
    session.add(message)
    await session.flush()
    touch_conversation_after_message(conversation, message)
    await append_conversation_event(
        session,
        conversation=conversation,
        event_type=ConversationEventType.MESSAGE_LOGGED,
        description="Mensagem enviada pela API oficial da Meta.",
        actor_user_id=actor.user.id,
        metadata={"message_id": str(message.id), "provider_message_id": provider_message_id},
    )
    return message


async def _mark_webhook_failure(
    session: AsyncSession,
    *,
    event: WebhookEvent,
    credential: ChannelCredential | None,
    error: Exception,
) -> None:
    if credential:
        credential.last_error_at = datetime.now(timezone.utc)
        credential.status_payload = {**credential.status_payload, "last_error": str(error)}
    event.processing_status = "failed"
    event.processing_notes = str(error)
    event.processed_at = datetime.now(timezone.utc)
    await session.commit()


async def _queue_webhook_event(
    session: AsyncSession,
    *,
    event: WebhookEvent,
    credential: ChannelCredential | None,
) -> WebhookAck:
    event.processing_status = "queued"
    event.processing_notes = "Evento enfileirado para processamento assincrono."
    await session.commit()

    try:
        enqueue_meta_webhook_event(event.id)
        return WebhookAck(
            message="Webhook enfileirado para processamento.",
            event_id=event.id,
            processing_status=event.processing_status,
        )
    except Exception as exc:
        event.processing_status = "processing"
        event.processing_notes = f"Fila indisponivel; executando fallback inline. {exc}"
        await session.flush()
        try:
            automation_execution_ids = await process_incoming_webhook_event(session, event)
        except Exception as inline_exc:
            await _mark_webhook_failure(session, event=event, credential=credential, error=inline_exc)
            raise
        await session.commit()
        for execution_id in automation_execution_ids:
            try:
                enqueue_automation_execution(execution_id)
            except Exception:
                continue
        return WebhookAck(
            message="Webhook processado em modo de contingencia.",
            event_id=event.id,
            processing_status=event.processing_status,
        )


@router.get("/webhooks")
async def verify_webhook_global(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
) -> Response:
    expected_token = get_verify_token(None)
    if hub_mode == "subscribe" and expected_token and hub_verify_token == expected_token:
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token de verificacao invalido.")


@router.get("/webhooks/{channel_id}")
async def verify_webhook_channel(
    channel_id: UUID,
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    credential = await get_channel_credential(session, channel_id)
    if not credential:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credencial nao encontrada para o canal.")
    expected_token = get_verify_token(credential)
    if hub_mode == "subscribe" and expected_token and hub_verify_token == expected_token:
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token de verificacao invalido.")


@router.post("/webhooks", response_model=WebhookAck)
async def receive_webhook_global(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    x_hub_signature_256: str | None = Header(default=None),
) -> WebhookAck:
    raw_body = await request.body()
    payload = await request.json()
    if payload.get("object") != "whatsapp_business_account":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Objeto de webhook nao suportado.")

    credential = await _resolve_webhook_credential(session, explicit_channel_id=None, payload=payload)
    app_secret = get_app_secret(credential)
    signature_valid = verify_meta_signature(raw_body, x_hub_signature_256, app_secret)
    if app_secret and not signature_valid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Assinatura de webhook invalida.")

    event = WebhookEvent(
        channel_id=credential.channel_id if credential else None,
        phone_number_id=extract_phone_number_id(payload),
        payload=payload,
        headers={key: value for key, value in request.headers.items()},
        signature_valid=signature_valid,
        processing_status="queued",
        processing_notes="Evento recebido.",
    )
    session.add(event)
    await session.flush()
    return await _queue_webhook_event(session, event=event, credential=credential)


@router.post("/webhooks/{channel_id}", response_model=WebhookAck)
async def receive_webhook_channel(
    channel_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    x_hub_signature_256: str | None = Header(default=None),
) -> WebhookAck:
    raw_body = await request.body()
    payload = await request.json()
    if payload.get("object") != "whatsapp_business_account":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Objeto de webhook nao suportado.")

    credential = await get_channel_credential(session, channel_id)
    if not credential:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credencial nao encontrada para o canal.")
    app_secret = get_app_secret(credential)
    signature_valid = verify_meta_signature(raw_body, x_hub_signature_256, app_secret)
    if app_secret and not signature_valid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Assinatura de webhook invalida.")

    event = WebhookEvent(
        channel_id=credential.channel_id,
        phone_number_id=extract_phone_number_id(payload),
        payload=payload,
        headers={key: value for key, value in request.headers.items()},
        signature_valid=signature_valid,
        processing_status="queued",
        processing_notes="Evento recebido.",
    )
    session.add(event)
    await session.flush()
    return await _queue_webhook_event(session, event=event, credential=credential)


@router.get("/channels/{channel_id}/credentials", response_model=ChannelCredentialRead)
async def read_channel_credential(
    channel_id: UUID,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> ChannelCredentialRead:
    channel = await _load_channel(session, channel_id)
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Canal nao encontrado.")
    _ensure_company_meta_access(actor, channel, manage=False)
    credential = await get_channel_credential(session, channel_id)
    if not credential:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credencial nao cadastrada para este canal.")
    return _serialize_credential(credential)


@router.put("/channels/{channel_id}/credentials", response_model=ChannelCredentialRead)
async def upsert_channel_credential(
    channel_id: UUID,
    payload: ChannelCredentialUpsert,
    request: Request,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> ChannelCredentialRead:
    channel = await _load_channel(session, channel_id)
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Canal nao encontrado.")
    _ensure_company_meta_access(actor, channel, manage=True)

    duplicate_channel = await session.scalar(
        select(WhatsAppChannel).where(
            WhatsAppChannel.external_phone_number_id == payload.phone_number_id.strip(),
            WhatsAppChannel.id != channel.id,
        )
    )
    if duplicate_channel:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phone Number ID ja vinculado a outro canal.")

    credential = await get_channel_credential(session, channel_id)
    if credential is None:
        credential = ChannelCredential(channel_id=channel.id)
        credential.channel = channel
        session.add(credential)

    channel.external_phone_number_id = payload.phone_number_id.strip()
    credential.app_id = payload.app_id.strip()
    credential.business_account_id = payload.business_account_id.strip()
    credential.graph_api_version = payload.graph_api_version.strip()
    credential.webhook_callback_url = payload.webhook_callback_url.strip()
    credential.is_active = payload.is_active
    set_credential_secrets(
        credential,
        access_token=payload.access_token,
        app_secret=payload.app_secret,
        webhook_verify_token=payload.webhook_verify_token,
    )
    await session.flush()
    await record_audit_log(
        session,
        action="meta.credentials.upserted",
        resource_type="channel_credential",
        actor_user_id=actor.user.id,
        resource_id=str(credential.id),
        company_id=channel.company_id,
        store_id=channel.store_id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"channel_id": str(channel.id), "phone_number_id": channel.external_phone_number_id},
    )
    await session.commit()
    await session.refresh(credential)
    return _serialize_credential(credential)


@router.get("/channels/{channel_id}/templates", response_model=list[MessageTemplateRead])
async def list_channel_templates(
    channel_id: UUID,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> list[MessageTemplateRead]:
    channel = await _load_channel(session, channel_id)
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Canal nao encontrado.")
    _ensure_company_meta_access(actor, channel, manage=False)
    templates = (
        await session.scalars(
            select(MessageTemplate)
            .where(MessageTemplate.channels.any(id=channel.id))
            .order_by(MessageTemplate.name.asc(), MessageTemplate.language_code.asc())
        )
    ).unique().all()
    return [_serialize_template(item) for item in templates]


@router.post("/channels/{channel_id}/templates/sync", response_model=TemplatesSyncResponse)
async def sync_channel_templates(
    channel_id: UUID,
    request: Request,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> TemplatesSyncResponse:
    channel = await _load_channel(session, channel_id)
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Canal nao encontrado.")
    _ensure_company_meta_access(actor, channel, manage=True)

    credential = await get_channel_credential(session, channel_id)
    if not credential or not credential.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credencial Meta inativa para este canal.")

    try:
        remote_templates = await WhatsAppCloudAPIClient(credential).list_templates()
        credential.last_healthcheck_at = datetime.now(timezone.utc)
        credential.last_error_at = None
    except (MetaAPIConfigurationError, MetaAPIRequestError) as exc:
        credential.last_error_at = datetime.now(timezone.utc)
        credential.status_payload = {"last_error": str(exc)}
        await session.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    synced: list[MessageTemplate] = []
    for item in remote_templates:
        name = item.get("name", "").strip()
        language_value = item.get("language") or item.get("language_code") or ""
        if isinstance(language_value, dict):
            language_code = str(language_value.get("code", "")).strip()
        else:
            language_code = str(language_value).strip()
        if not name or not language_code:
            continue
        template = await session.scalar(
            select(MessageTemplate).where(
                MessageTemplate.name == name,
                MessageTemplate.language_code == language_code,
            )
        )
        if template is None:
            template = MessageTemplate(name=name, language_code=language_code, category="UNKNOWN")
            session.add(template)
            await session.flush()
        template.meta_template_id = str(item.get("id", "") or item.get("meta_template_id", ""))
        template.category = str(item.get("category", "") or "UNKNOWN")
        template.status = str(item.get("status", "") or "UNKNOWN")
        template.components_schema = {"components": item.get("components", [])}
        template.last_synced_at = datetime.now(timezone.utc)
        if channel not in template.channels:
            template.channels.append(channel)
        synced.append(template)

    credential.status_payload = {
        "last_template_sync_count": len(synced),
        "last_template_sync_at": datetime.now(timezone.utc).isoformat(),
    }
    await record_audit_log(
        session,
        action="meta.templates.synced",
        resource_type="channel_credential",
        actor_user_id=actor.user.id,
        resource_id=str(credential.id),
        company_id=channel.company_id,
        store_id=channel.store_id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"synced_count": len(synced)},
    )
    await session.commit()
    return TemplatesSyncResponse(
        synced_count=len(synced),
        templates=[_serialize_template(item) for item in synced],
    )


@router.post("/conversations/{conversation_id}/messages/text", response_model=OutboundMessageResponse)
async def send_text_message(
    conversation_id: UUID,
    payload: SendTextMessageRequest,
    request: Request,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> OutboundMessageResponse:
    conversation = await _load_conversation_for_meta(session, conversation_id)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa nao encontrada.")
    if not actor.has_permission("crm.manage", company_id=conversation.company_id, store_id=conversation.store_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para responder esta conversa.")

    credential = await get_channel_credential(session, conversation.channel_id)
    if not credential or not credential.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credencial Meta inativa para este canal.")
    if not is_customer_service_window_open(conversation):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A janela de atendimento de 24 horas esta fechada. Use um template aprovado.",
        )

    body = payload.body.strip()
    try:
        provider_response = await WhatsAppCloudAPIClient(credential).send_text_message(
            to=to_whatsapp_recipient(conversation.contact.phone_number_e164),
            body=body,
            preview_url=payload.preview_url,
        )
        credential.last_healthcheck_at = datetime.now(timezone.utc)
        credential.last_error_at = None
    except (MetaAPIConfigurationError, MetaAPIRequestError) as exc:
        credential.last_error_at = datetime.now(timezone.utc)
        credential.status_payload = {"last_error": str(exc)}
        await session.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    provider_messages = provider_response.get("messages", [])
    provider_message_id = provider_messages[0].get("id") if provider_messages else None
    sent_at = datetime.now(timezone.utc)
    message = await _persist_outbound_message(
        session,
        conversation=conversation,
        actor=actor,
        direction=MessageDirection.OUTBOUND,
        sender_type=MessageSenderType.AGENT,
        message_type=MessageType.TEXT,
        delivery_status=MessageDeliveryStatus.SENT,
        body=body,
        provider_message_id=provider_message_id,
        provider_response=provider_response,
        sent_at=sent_at,
    )
    await record_audit_log(
        session,
        action="meta.messages.text_sent",
        resource_type="conversation_message",
        actor_user_id=actor.user.id,
        resource_id=str(message.id),
        company_id=conversation.company_id,
        store_id=conversation.store_id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"conversation_id": str(conversation.id), "provider_message_id": provider_message_id},
    )
    await session.commit()
    return OutboundMessageResponse(
        conversation_id=conversation.id,
        conversation_message_id=message.id,
        channel_id=conversation.channel_id,
        provider_message_id=provider_message_id,
        delivery_status=message.delivery_status.value,
        inside_customer_service_window=True,
        provider_response=provider_response,
        sent_at=sent_at,
    )


@router.post("/conversations/{conversation_id}/messages/template", response_model=OutboundMessageResponse)
async def send_template_message(
    conversation_id: UUID,
    payload: SendTemplateMessageRequest,
    request: Request,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> OutboundMessageResponse:
    conversation = await _load_conversation_for_meta(session, conversation_id)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa nao encontrada.")
    if not actor.has_permission("crm.manage", company_id=conversation.company_id, store_id=conversation.store_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para responder esta conversa.")

    credential = await get_channel_credential(session, conversation.channel_id)
    if not credential or not credential.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credencial Meta inativa para este canal.")

    template = await session.scalar(
        select(MessageTemplate).where(
            MessageTemplate.name == payload.template_name,
            MessageTemplate.language_code == payload.language_code,
            MessageTemplate.channels.any(id=conversation.channel_id),
        )
    )
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template nao encontrado ou nao vinculado a este canal.",
        )

    try:
        provider_response = await WhatsAppCloudAPIClient(credential).send_template_message(
            to=to_whatsapp_recipient(conversation.contact.phone_number_e164),
            template_name=payload.template_name,
            language_code=payload.language_code,
            components=payload.components,
        )
        credential.last_healthcheck_at = datetime.now(timezone.utc)
        credential.last_error_at = None
    except (MetaAPIConfigurationError, MetaAPIRequestError) as exc:
        credential.last_error_at = datetime.now(timezone.utc)
        credential.status_payload = {"last_error": str(exc)}
        await session.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    provider_messages = provider_response.get("messages", [])
    provider_message_id = provider_messages[0].get("id") if provider_messages else None
    sent_at = datetime.now(timezone.utc)
    message = await _persist_outbound_message(
        session,
        conversation=conversation,
        actor=actor,
        direction=MessageDirection.OUTBOUND,
        sender_type=MessageSenderType.AGENT,
        message_type=MessageType.TEMPLATE,
        delivery_status=MessageDeliveryStatus.SENT,
        body=f"[TEMPLATE] {payload.template_name}:{payload.language_code}",
        provider_message_id=provider_message_id,
        provider_response={**provider_response, "template_name": payload.template_name, "language_code": payload.language_code},
        sent_at=sent_at,
    )
    inside_window = is_customer_service_window_open(conversation)
    await record_audit_log(
        session,
        action="meta.messages.template_sent",
        resource_type="conversation_message",
        actor_user_id=actor.user.id,
        resource_id=str(message.id),
        company_id=conversation.company_id,
        store_id=conversation.store_id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"conversation_id": str(conversation.id), "provider_message_id": provider_message_id},
    )
    await session.commit()
    return OutboundMessageResponse(
        conversation_id=conversation.id,
        conversation_message_id=message.id,
        channel_id=conversation.channel_id,
        provider_message_id=provider_message_id,
        delivery_status=message.delivery_status.value,
        inside_customer_service_window=inside_window,
        provider_response=provider_response,
        sent_at=sent_at,
    )
