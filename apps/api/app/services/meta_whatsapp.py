from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.config import settings
from app.core.security import decrypt_secret, encrypt_secret
from app.models.crm import Contact, Conversation, ConversationMessage, WhatsAppChannel
from app.models.enums import (
    AutomationTriggerType,
    ConversationEventType,
    ConversationStatus,
    MessageDeliveryStatus,
    MessageDirection,
    MessageSenderType,
    MessageType,
)
from app.models.meta import ChannelCredential, MessageTemplate, WebhookEvent
from app.services.automation_runtime import build_automation_executions_for_trigger
from app.services.crm import (
    append_conversation_event,
    conversation_detail_query_options,
    touch_conversation_after_message,
)


class MetaAPIConfigurationError(RuntimeError):
    """Erro de configuracao da integracao oficial da Meta."""


class MetaAPIRequestError(RuntimeError):
    """Erro retornado pela Graph API da Meta."""

    def __init__(self, message: str, *, status_code: int | None = None, response_payload: Any | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_payload = response_payload


def credential_query():
    return select(ChannelCredential).options(joinedload(ChannelCredential.channel))


async def get_channel_credential(session: AsyncSession, channel_id: UUID) -> ChannelCredential | None:
    return await session.scalar(credential_query().where(ChannelCredential.channel_id == channel_id))


async def get_credential_by_phone_number_id(session: AsyncSession, phone_number_id: str) -> ChannelCredential | None:
    stmt = (
        credential_query()
        .join(WhatsAppChannel, WhatsAppChannel.id == ChannelCredential.channel_id)
        .where(WhatsAppChannel.external_phone_number_id == phone_number_id)
    )
    return await session.scalar(stmt)


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "*" * len(value)
    return f"{'*' * max(len(value) - 4, 4)}{value[-4:]}"


def get_access_token(credential: ChannelCredential) -> str:
    if credential.encrypted_access_token:
        return decrypt_secret(credential.encrypted_access_token)
    raise MetaAPIConfigurationError("Token de acesso da Meta nao configurado para este canal.")


def get_app_secret(credential: ChannelCredential | None = None) -> str:
    if credential and credential.encrypted_app_secret:
        return decrypt_secret(credential.encrypted_app_secret)
    return settings.meta_global_app_secret


def get_verify_token(credential: ChannelCredential | None = None) -> str:
    if credential and credential.encrypted_webhook_verify_token:
        return decrypt_secret(credential.encrypted_webhook_verify_token)
    return settings.meta_global_verify_token


def set_credential_secrets(
    credential: ChannelCredential,
    *,
    access_token: str | None = None,
    app_secret: str | None = None,
    webhook_verify_token: str | None = None,
) -> None:
    if access_token is not None:
        token = access_token.strip()
        credential.encrypted_access_token = encrypt_secret(token)
        credential.access_token_last4 = token[-4:] if token else ""
    if app_secret is not None:
        credential.encrypted_app_secret = encrypt_secret(app_secret.strip())
    if webhook_verify_token is not None:
        token = webhook_verify_token.strip()
        credential.encrypted_webhook_verify_token = encrypt_secret(token)
        credential.verify_token_hint = mask_secret(token)


def iter_webhook_values(payload: dict[str, Any]):
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            if value:
                yield value


def extract_phone_number_id(payload: dict[str, Any]) -> str:
    for value in iter_webhook_values(payload):
        metadata = value.get("metadata", {})
        if metadata.get("phone_number_id"):
            return str(metadata["phone_number_id"])
    return ""


def extract_inbound_text_body(message: dict[str, Any]) -> str:
    message_type = message.get("type", "")
    if message_type == "text":
        return message.get("text", {}).get("body", "")
    if message_type == "button":
        return message.get("button", {}).get("text", "")
    if message_type == "interactive":
        interactive = message.get("interactive", {})
        if "button_reply" in interactive:
            return interactive["button_reply"].get("title", "")
        if "list_reply" in interactive:
            return interactive["list_reply"].get("title", "")
    if message_type == "image":
        return message.get("image", {}).get("caption", "")
    if message_type == "document":
        return message.get("document", {}).get("caption", "")
    if message_type == "video":
        return message.get("video", {}).get("caption", "")
    if message_type == "audio":
        return "[Audio recebido]"
    return ""


def meta_message_type_to_internal(value: str) -> MessageType:
    mapped = {
        "text": MessageType.TEXT,
        "image": MessageType.IMAGE,
        "audio": MessageType.AUDIO,
        "video": MessageType.VIDEO,
        "document": MessageType.DOCUMENT,
        "interactive": MessageType.INTERACTIVE,
        "button": MessageType.INTERACTIVE,
    }
    return mapped.get(value, MessageType.TEXT)


def map_provider_status(value: str) -> MessageDeliveryStatus:
    mapped = {
        "sent": MessageDeliveryStatus.SENT,
        "delivered": MessageDeliveryStatus.DELIVERED,
        "read": MessageDeliveryStatus.READ,
        "failed": MessageDeliveryStatus.FAILED,
    }
    return mapped.get(value, MessageDeliveryStatus.PENDING)


def normalize_wa_number(value: str) -> str:
    digits = "".join(char for char in value if char.isdigit())
    if not digits:
        return value
    return f"+{digits}"


def to_whatsapp_recipient(value: str) -> str:
    digits = "".join(char for char in value if char.isdigit())
    return digits or value


def is_customer_service_window_open(conversation: Conversation, *, reference_time: datetime | None = None) -> bool:
    if not conversation.last_customer_message_at:
        return False
    reference = reference_time or datetime.now(timezone.utc)
    return conversation.last_customer_message_at >= reference.replace(microsecond=0) - timedelta(hours=24)


class WhatsAppCloudAPIClient:
    def __init__(self, credential: ChannelCredential) -> None:
        self.credential = credential
        self.channel = credential.channel
        self.phone_number_id = self.channel.external_phone_number_id
        self.graph_api_version = credential.graph_api_version or settings.meta_default_graph_api_version
        self.base_url = f"{settings.meta_graph_api_base_url.rstrip('/')}/{self.graph_api_version}"
        self.access_token = get_access_token(credential)
        if not self.phone_number_id:
            raise MetaAPIConfigurationError("Phone Number ID nao configurado para este canal.")

    async def request(
        self,
        method: str,
        path: str | None = None,
        *,
        params: dict[str, Any] | None = None,
        json_payload: dict[str, Any] | None = None,
        absolute_url: str | None = None,
    ) -> dict[str, Any]:
        url = absolute_url or f"{self.base_url}/{path.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(method, url, headers=headers, params=params, json=json_payload)
        try:
            payload = response.json()
        except ValueError:
            payload = {"raw": response.text}
        if response.is_error:
            raise MetaAPIRequestError(
                f"Erro na Graph API ({response.status_code}).",
                status_code=response.status_code,
                response_payload=payload,
            )
        return payload

    async def send_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request("POST", f"{self.phone_number_id}/messages", json_payload=payload)

    async def send_text_message(self, *, to: str, body: str, preview_url: bool = False) -> dict[str, Any]:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {
                "preview_url": preview_url,
                "body": body,
            },
        }
        return await self.send_payload(payload)

    async def send_template_message(
        self,
        *,
        to: str,
        template_name: str,
        language_code: str,
        components: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
            },
        }
        if components:
            payload["template"]["components"] = components
        return await self.send_payload(payload)

    async def list_templates(self) -> list[dict[str, Any]]:
        if not self.credential.business_account_id:
            raise MetaAPIConfigurationError("Business Account ID nao configurado para sincronizar templates.")

        items: list[dict[str, Any]] = []
        next_url: str | None = None
        while True:
            if next_url:
                payload = await self.request("GET", absolute_url=next_url)
            else:
                payload = await self.request(
                    "GET",
                    f"{self.credential.business_account_id}/message_templates",
                    params={"limit": 100},
                )
            items.extend(payload.get("data", []))
            next_url = payload.get("paging", {}).get("next")
            if not next_url:
                break
        return items


async def find_or_create_inbound_contact(
    session: AsyncSession,
    *,
    channel: WhatsAppChannel,
    wa_id: str,
    profile_name: str | None,
) -> Contact:
    normalized_phone = normalize_wa_number(wa_id)
    contact = await session.scalar(
        select(Contact).where(
            Contact.company_id == channel.company_id,
            Contact.phone_number_e164 == normalized_phone,
        )
    )
    if contact:
        if profile_name and contact.full_name == contact.phone_number_e164:
            contact.full_name = profile_name
        if contact.primary_store_id is None:
            contact.primary_store_id = channel.store_id
        return contact

    contact = Contact(
        company_id=channel.company_id,
        primary_store_id=channel.store_id,
        full_name=profile_name or normalized_phone,
        phone_number_e164=normalized_phone,
        source="whatsapp_inbound",
    )
    session.add(contact)
    await session.flush()
    return contact


async def find_or_create_open_conversation(
    session: AsyncSession,
    *,
    channel: WhatsAppChannel,
    contact: Contact,
) -> tuple[Conversation, bool]:
    stmt = (
        select(Conversation)
        .where(
            Conversation.company_id == channel.company_id,
            Conversation.store_id == channel.store_id,
            Conversation.channel_id == channel.id,
            Conversation.contact_id == contact.id,
            Conversation.status.notin_(
                [ConversationStatus.CLOSED, ConversationStatus.LOST, ConversationStatus.CANCELED]
            ),
        )
        .order_by(Conversation.opened_at.desc())
        .options(*conversation_detail_query_options())
    )
    conversation = await session.scalar(stmt)
    if conversation:
        return conversation, False

    conversation = Conversation(
        company_id=channel.company_id,
        store_id=channel.store_id,
        channel_id=channel.id,
        contact_id=contact.id,
        source="whatsapp",
        status=ConversationStatus.NEW,
        opened_at=datetime.now(timezone.utc),
    )
    conversation.channel = channel
    conversation.contact = contact
    session.add(conversation)
    await session.flush()
    await append_conversation_event(
        session,
        conversation=conversation,
        event_type=ConversationEventType.OPENED,
        description="Conversa aberta por mensagem inbound da Meta Cloud API.",
    )
    return conversation, True


async def process_incoming_webhook_event(session: AsyncSession, event: WebhookEvent) -> list[str]:
    payload = event.payload
    automation_execution_ids: list[str] = []
    phone_number_id = event.phone_number_id or extract_phone_number_id(payload)
    credential = None
    if event.channel_id:
        credential = await get_channel_credential(session, event.channel_id)
    if credential is None and phone_number_id:
        credential = await get_credential_by_phone_number_id(session, phone_number_id)
    if credential is None:
        event.processing_status = "ignored"
        event.processing_notes = "Canal nao encontrado para o phone_number_id informado."
        event.processed_at = datetime.now(timezone.utc)
        return automation_execution_ids

    channel = credential.channel
    if not channel:
        event.processing_status = "ignored"
        event.processing_notes = "Credencial sem canal vinculado."
        event.processed_at = datetime.now(timezone.utc)
        return automation_execution_ids
    credential.last_healthcheck_at = datetime.now(timezone.utc)
    credential.last_error_at = None

    for value in iter_webhook_values(payload):
        contacts_payload = value.get("contacts", [])
        profile_name = ""
        if contacts_payload:
            profile_name = contacts_payload[0].get("profile", {}).get("name", "")

        for message in value.get("messages", []):
            wa_id = str(message.get("from", "")).strip()
            if not wa_id:
                continue
            contact = await find_or_create_inbound_contact(
                session,
                channel=channel,
                wa_id=wa_id,
                profile_name=profile_name,
            )
            conversation, conversation_created = await find_or_create_open_conversation(
                session,
                channel=channel,
                contact=contact,
            )
            provider_message_id = message.get("id")
            existing = None
            if provider_message_id:
                existing = await session.scalar(
                    select(ConversationMessage).where(
                        ConversationMessage.channel_id == channel.id,
                        ConversationMessage.provider_message_id == str(provider_message_id),
                    )
                )
            if existing:
                continue

            inbound_message = ConversationMessage(
                company_id=channel.company_id,
                store_id=channel.store_id,
                channel_id=channel.id,
                conversation_id=conversation.id,
                direction=MessageDirection.INBOUND,
                sender_type=MessageSenderType.CUSTOMER,
                message_type=meta_message_type_to_internal(message.get("type", "text")),
                delivery_status=MessageDeliveryStatus.DELIVERED,
                provider_message_id=str(provider_message_id) if provider_message_id else None,
                text_body=extract_inbound_text_body(message),
                is_human=False,
                metadata_json=message,
                sent_at=datetime.now(timezone.utc),
            )
            inbound_message.conversation = conversation
            inbound_message.channel = channel
            session.add(inbound_message)
            await session.flush()
            touch_conversation_after_message(conversation, inbound_message)
            await append_conversation_event(
                session,
                conversation=conversation,
                event_type=ConversationEventType.MESSAGE_LOGGED,
                description="Mensagem inbound recebida via webhook oficial da Meta.",
                metadata={"message_id": str(inbound_message.id), "provider_message_id": inbound_message.provider_message_id},
            )
            if conversation_created:
                opened_executions = await build_automation_executions_for_trigger(
                    session,
                    trigger_type=AutomationTriggerType.CONVERSATION_OPENED,
                    conversation=conversation,
                    metadata={
                        "origin": "meta.webhook",
                        "provider_message_id": inbound_message.provider_message_id,
                    },
                    reference_time=inbound_message.sent_at,
                )
                automation_execution_ids.extend(str(item.id) for item in opened_executions)
                out_of_hours_executions = await build_automation_executions_for_trigger(
                    session,
                    trigger_type=AutomationTriggerType.OUT_OF_HOURS,
                    conversation=conversation,
                    metadata={
                        "origin": "meta.webhook",
                        "provider_message_id": inbound_message.provider_message_id,
                    },
                    reference_time=inbound_message.sent_at,
                )
                automation_execution_ids.extend(str(item.id) for item in out_of_hours_executions)

        for status_payload in value.get("statuses", []):
            provider_message_id = str(status_payload.get("id", "")).strip()
            if not provider_message_id:
                continue
            message = await session.scalar(
                select(ConversationMessage)
                .where(
                    ConversationMessage.channel_id == channel.id,
                    ConversationMessage.provider_message_id == provider_message_id,
                )
                .options(selectinload(ConversationMessage.conversation))
            )
            if not message:
                continue
            mapped_status = map_provider_status(status_payload.get("status", "pending"))
            message.delivery_status = mapped_status
            status_time = status_payload.get("timestamp")
            occurred_at = None
            if status_time:
                try:
                    occurred_at = datetime.fromtimestamp(int(status_time), tz=timezone.utc)
                except (TypeError, ValueError):
                    occurred_at = datetime.now(timezone.utc)
            else:
                occurred_at = datetime.now(timezone.utc)

            if mapped_status == MessageDeliveryStatus.DELIVERED:
                message.delivered_at = occurred_at
            elif mapped_status == MessageDeliveryStatus.READ:
                message.read_at = occurred_at
            elif mapped_status == MessageDeliveryStatus.FAILED:
                message.failed_at = occurred_at
            message.metadata_json = {**message.metadata_json, "last_status_payload": status_payload}

    event.channel_id = channel.id
    event.processing_status = "processed"
    event.processing_notes = "Webhook processado com sucesso."
    event.processed_at = datetime.now(timezone.utc)
    return automation_execution_ids
