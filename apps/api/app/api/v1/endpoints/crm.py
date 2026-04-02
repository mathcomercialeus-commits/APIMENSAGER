from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor, request_ip
from app.core.database import get_db_session
from app.models.crm import (
    Contact,
    Conversation,
    ConversationAssignment,
    ConversationMessage,
    Tag,
    WhatsAppChannel,
    contact_tags,
)
from app.models.enums import (
    AutomationTriggerType,
    ContactStatus,
    ConversationEventType,
    ConversationPriority,
    ConversationStatus,
    MessageDeliveryStatus,
    MessageDirection,
    MessageSenderType,
    MessageType,
)
from app.models.platform import PlatformUser
from app.schemas.common import MessageResponse
from app.schemas.crm import (
    ContactCreate,
    ContactRead,
    ContactUpdate,
    ConversationAssign,
    ConversationCreate,
    ConversationEventRead,
    ConversationMessageCreate,
    ConversationMessageRead,
    ConversationNoteCreate,
    ConversationRead,
    ConversationStatusUpdate,
    ConversationSummaryRead,
    ConversationUpdate,
    TagCreate,
    TagRead,
)
from app.services.access import CurrentActor, get_company_or_404, get_store_or_404
from app.services.audit import record_audit_log
from app.services.automation_runtime import build_automation_executions_for_trigger
from app.services.crm import (
    append_conversation_event,
    contact_query_options,
    conversation_detail_query_options,
    conversation_query_options,
    ensure_user_can_access_store,
    release_open_assignment,
    serialize_contact,
    serialize_conversation,
    serialize_conversation_summary,
    serialize_event,
    serialize_message,
    serialize_tag,
    touch_conversation_after_message,
)
from app.workers.tasks import enqueue_automation_execution


router = APIRouter()


def _dispatch_automation_executions(executions) -> None:
    for execution in executions:
        try:
            enqueue_automation_execution(execution.id)
        except Exception:
            continue


async def _load_tag(session: AsyncSession, tag_id: UUID) -> Tag | None:
    return await session.scalar(select(Tag).where(Tag.id == tag_id))


async def _load_contact(session: AsyncSession, contact_id: UUID) -> Contact | None:
    return await session.scalar(
        select(Contact).where(Contact.id == contact_id).options(*contact_query_options())
    )


async def _load_conversation(
    session: AsyncSession,
    conversation_id: UUID,
    *,
    detailed: bool = False,
) -> Conversation | None:
    options = conversation_detail_query_options() if detailed else conversation_query_options()
    return await session.scalar(
        select(Conversation).where(Conversation.id == conversation_id).options(*options)
    )


def _actor_store_ids_for_company(actor: CurrentActor, company_id: UUID) -> list[UUID]:
    return [item for item, mapped_company_id in actor.store_to_company.items() if mapped_company_id == company_id]


def _can_view_company_contacts(actor: CurrentActor, company_id: UUID) -> bool:
    return actor.is_superadmin or company_id in actor.company_roles


def _ensure_tag_scope(tag: Tag, *, company_id: UUID, store_id: UUID | None) -> None:
    if tag.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tag fora do escopo da empresa.")
    if tag.store_id and store_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tag exige escopo de loja.")
    if tag.store_id and store_id and tag.store_id != store_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tag fora do escopo da loja.")


def _contact_view_allowed(actor: CurrentActor, contact: Contact) -> bool:
    if actor.is_superadmin or contact.company_id in actor.company_roles:
        return True
    if contact.primary_store_id:
        return actor.has_permission("contacts.view", company_id=contact.company_id, store_id=contact.primary_store_id)
    return False


@router.get("/tags", response_model=list[TagRead])
async def list_tags(
    company_id: UUID,
    store_id: UUID | None = Query(default=None),
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> list[TagRead]:
    company = await get_company_or_404(session, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa nao encontrada.")
    if store_id:
        store = await get_store_or_404(session, store_id)
        if not store or store.company_id != company.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Loja invalida para esta empresa.")
        if not actor.has_permission("crm.view", company_id=company.id, store_id=store.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem acesso ao CRM desta loja.")
    elif not actor.can_access_company(company.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem acesso a esta empresa.")

    stmt = select(Tag).where(Tag.company_id == company.id).order_by(Tag.name)
    if store_id:
        stmt = stmt.where(or_(Tag.store_id.is_(None), Tag.store_id == store_id))
    elif not _can_view_company_contacts(actor, company.id):
        store_ids = _actor_store_ids_for_company(actor, company.id)
        stmt = stmt.where(or_(Tag.store_id.is_(None), Tag.store_id.in_(store_ids)))

    tags = (await session.scalars(stmt)).all()
    return [serialize_tag(tag) for tag in tags]


@router.post("/tags", response_model=TagRead, status_code=status.HTTP_201_CREATED)
async def create_tag(
    payload: TagCreate,
    request: Request,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> TagRead:
    company = await get_company_or_404(session, payload.company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa nao encontrada.")

    store = None
    if payload.store_id:
        store = await get_store_or_404(session, payload.store_id)
        if not store or store.company_id != company.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Loja invalida para esta empresa.")
    if not actor.has_permission("crm.manage", company_id=company.id, store_id=store.id if store else None):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para criar tags.")

    tag = Tag(**payload.model_dump())
    tag.company = company
    tag.store = store
    session.add(tag)
    await session.flush()
    await record_audit_log(
        session,
        action="crm.tags.created",
        resource_type="tag",
        actor_user_id=actor.user.id,
        resource_id=str(tag.id),
        company_id=company.id,
        store_id=store.id if store else None,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
    )
    await session.commit()
    return serialize_tag(tag)


@router.get("/contacts", response_model=list[ContactRead])
async def list_contacts(
    company_id: UUID | None = Query(default=None),
    store_id: UUID | None = Query(default=None),
    search: str | None = Query(default=None),
    tag_id: UUID | None = Query(default=None),
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> list[ContactRead]:
    stmt = select(Contact).options(*contact_query_options()).order_by(Contact.full_name)
    if tag_id:
        stmt = stmt.join(contact_tags).where(contact_tags.c.tag_id == tag_id)
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Contact.full_name.ilike(pattern),
                Contact.phone_number_e164.ilike(pattern),
                Contact.email.ilike(pattern),
            )
        )

    if store_id:
        store = await get_store_or_404(session, store_id)
        if not store:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loja nao encontrada.")
        if not actor.has_permission("contacts.view", company_id=store.company_id, store_id=store.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem acesso aos contatos da loja.")
        stmt = stmt.where(Contact.company_id == store.company_id, Contact.primary_store_id == store.id)
    elif company_id:
        company = await get_company_or_404(session, company_id)
        if not company:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa nao encontrada.")
        if _can_view_company_contacts(actor, company.id):
            stmt = stmt.where(Contact.company_id == company.id)
        elif actor.can_access_company(company.id):
            store_ids = _actor_store_ids_for_company(actor, company.id)
            stmt = stmt.where(Contact.company_id == company.id, Contact.primary_store_id.in_(store_ids))
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem acesso aos contatos da empresa.")
    elif not actor.is_superadmin:
        company_ids = list(actor.company_roles.keys())
        store_ids = list(actor.store_roles.keys())
        if company_ids:
            company_filter = Contact.company_id.in_(company_ids)
            store_filter = Contact.primary_store_id.in_(store_ids) if store_ids else Contact.id.is_(None)
            stmt = stmt.where(or_(company_filter, store_filter))
        elif store_ids:
            stmt = stmt.where(Contact.primary_store_id.in_(store_ids))
        else:
            return []

    contacts = (await session.scalars(stmt)).unique().all()
    return [serialize_contact(contact) for contact in contacts]


@router.post("/contacts", response_model=ContactRead, status_code=status.HTTP_201_CREATED)
async def create_contact(
    payload: ContactCreate,
    request: Request,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> ContactRead:
    company = await get_company_or_404(session, payload.company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa nao encontrada.")

    primary_store = None
    if payload.primary_store_id:
        primary_store = await get_store_or_404(session, payload.primary_store_id)
        if not primary_store or primary_store.company_id != company.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Loja invalida para esta empresa.")

    try:
        contact_status = ContactStatus(payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Status do contato invalido.") from exc

    if not actor.has_permission(
        "contacts.manage",
        company_id=company.id,
        store_id=primary_store.id if primary_store else None,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para criar contatos.")

    tags: list[Tag] = []
    for tag_id in payload.tag_ids:
        tag = await _load_tag(session, tag_id)
        if not tag:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tag {tag_id} nao encontrada.")
        _ensure_tag_scope(tag, company_id=company.id, store_id=primary_store.id if primary_store else None)
        tags.append(tag)

    contact = Contact(
        company_id=company.id,
        primary_store_id=primary_store.id if primary_store else None,
        full_name=payload.full_name,
        phone_number_e164=payload.phone_number_e164,
        alternate_phone=payload.alternate_phone,
        email=payload.email,
        document_number=payload.document_number,
        status=contact_status,
        source=payload.source,
        notes=payload.notes,
    )
    contact.company = company
    contact.primary_store = primary_store
    contact.tags = tags
    session.add(contact)
    await session.flush()

    await record_audit_log(
        session,
        action="crm.contacts.created",
        resource_type="contact",
        actor_user_id=actor.user.id,
        resource_id=str(contact.id),
        company_id=company.id,
        store_id=primary_store.id if primary_store else None,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
    )
    await session.commit()
    contact = await _load_contact(session, contact.id)
    return serialize_contact(contact)


@router.get("/contacts/{contact_id}", response_model=ContactRead)
async def get_contact(
    contact_id: UUID,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> ContactRead:
    contact = await _load_contact(session, contact_id)
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contato nao encontrado.")
    if not _contact_view_allowed(actor, contact):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem acesso a este contato.")
    return serialize_contact(contact)


@router.patch("/contacts/{contact_id}", response_model=ContactRead)
async def update_contact(
    contact_id: UUID,
    payload: ContactUpdate,
    request: Request,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> ContactRead:
    contact = await _load_contact(session, contact_id)
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contato nao encontrado.")
    if not actor.has_permission(
        "contacts.manage",
        company_id=contact.company_id,
        store_id=contact.primary_store_id,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para alterar este contato.")

    changed_fields = payload.model_dump(exclude_unset=True)
    status_value = changed_fields.pop("status", None)
    if status_value is not None:
        try:
            contact.status = ContactStatus(status_value)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Status do contato invalido.") from exc

    primary_store_present = "primary_store_id" in changed_fields
    primary_store_id = changed_fields.pop("primary_store_id", None)
    if primary_store_present:
        if primary_store_id:
            store = await get_store_or_404(session, primary_store_id)
            if not store or store.company_id != contact.company_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Loja invalida para este contato.")
            contact.primary_store_id = store.id
            contact.primary_store = store
        else:
            contact.primary_store_id = None
            contact.primary_store = None

    nullable_fields = {"alternate_phone", "email", "document_number"}
    for field, value in changed_fields.items():
        if value is None and field not in nullable_fields:
            continue
        setattr(contact, field, value)

    await record_audit_log(
        session,
        action="crm.contacts.updated",
        resource_type="contact",
        actor_user_id=actor.user.id,
        resource_id=str(contact.id),
        company_id=contact.company_id,
        store_id=contact.primary_store_id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"fields": sorted(payload.model_dump(exclude_unset=True).keys())},
    )
    await session.commit()
    contact = await _load_contact(session, contact.id)
    return serialize_contact(contact)


@router.post("/contacts/{contact_id}/tags/{tag_id}", response_model=ContactRead)
async def attach_tag_to_contact(
    contact_id: UUID,
    tag_id: UUID,
    request: Request,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> ContactRead:
    contact = await _load_contact(session, contact_id)
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contato nao encontrado.")
    if not actor.has_permission("contacts.manage", company_id=contact.company_id, store_id=contact.primary_store_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para etiquetar este contato.")

    tag = await _load_tag(session, tag_id)
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag nao encontrada.")
    _ensure_tag_scope(tag, company_id=contact.company_id, store_id=contact.primary_store_id)

    if tag not in contact.tags:
        contact.tags.append(tag)

    await record_audit_log(
        session,
        action="crm.contacts.tag_attached",
        resource_type="contact",
        actor_user_id=actor.user.id,
        resource_id=str(contact.id),
        company_id=contact.company_id,
        store_id=contact.primary_store_id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"tag_id": str(tag.id)},
    )
    await session.commit()
    contact = await _load_contact(session, contact.id)
    return serialize_contact(contact)


@router.delete("/contacts/{contact_id}/tags/{tag_id}", response_model=ContactRead)
async def remove_tag_from_contact(
    contact_id: UUID,
    tag_id: UUID,
    request: Request,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> ContactRead:
    contact = await _load_contact(session, contact_id)
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contato nao encontrado.")
    if not actor.has_permission("contacts.manage", company_id=contact.company_id, store_id=contact.primary_store_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para etiquetar este contato.")

    tag = await _load_tag(session, tag_id)
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag nao encontrada.")

    contact.tags = [item for item in contact.tags if item.id != tag.id]
    await record_audit_log(
        session,
        action="crm.contacts.tag_removed",
        resource_type="contact",
        actor_user_id=actor.user.id,
        resource_id=str(contact.id),
        company_id=contact.company_id,
        store_id=contact.primary_store_id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"tag_id": str(tag.id)},
    )
    await session.commit()
    contact = await _load_contact(session, contact.id)
    return serialize_contact(contact)


@router.get("/conversations", response_model=list[ConversationSummaryRead])
async def list_conversations(
    company_id: UUID | None = Query(default=None),
    store_id: UUID | None = Query(default=None),
    channel_id: UUID | None = Query(default=None),
    assigned_user_id: UUID | None = Query(default=None),
    contact_id: UUID | None = Query(default=None),
    status_code: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> list[ConversationSummaryRead]:
    stmt = (
        select(Conversation)
        .options(*conversation_query_options())
        .order_by(Conversation.last_message_at.desc().nullslast(), Conversation.opened_at.desc())
    )

    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.join(Contact).where(
            or_(
                Contact.full_name.ilike(pattern),
                Contact.phone_number_e164.ilike(pattern),
                Conversation.subject.ilike(pattern),
            )
        )
    if contact_id:
        stmt = stmt.where(Conversation.contact_id == contact_id)
    if channel_id:
        stmt = stmt.where(Conversation.channel_id == channel_id)
    if assigned_user_id:
        stmt = stmt.where(Conversation.assigned_user_id == assigned_user_id)
    if status_code:
        try:
            conversation_status = ConversationStatus(status_code)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Status da conversa invalido.") from exc
        stmt = stmt.where(Conversation.status == conversation_status)

    if store_id:
        store = await get_store_or_404(session, store_id)
        if not store:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loja nao encontrada.")
        if not actor.has_permission("crm.view", company_id=store.company_id, store_id=store.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem acesso ao atendimento desta loja.")
        stmt = stmt.where(Conversation.store_id == store.id)
    elif company_id:
        company = await get_company_or_404(session, company_id)
        if not company:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa nao encontrada.")
        if actor.is_superadmin or company.id in actor.company_roles:
            stmt = stmt.where(Conversation.company_id == company.id)
        elif actor.can_access_company(company.id):
            store_ids = _actor_store_ids_for_company(actor, company.id)
            stmt = stmt.where(Conversation.company_id == company.id, Conversation.store_id.in_(store_ids))
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem acesso ao atendimento da empresa.")
    elif not actor.is_superadmin:
        company_ids = list(actor.company_roles.keys())
        store_ids = list(actor.store_roles.keys())
        if company_ids and store_ids:
            stmt = stmt.where(or_(Conversation.company_id.in_(company_ids), Conversation.store_id.in_(store_ids)))
        elif company_ids:
            stmt = stmt.where(Conversation.company_id.in_(company_ids))
        elif store_ids:
            stmt = stmt.where(Conversation.store_id.in_(store_ids))
        else:
            return []

    conversations = (await session.scalars(stmt)).unique().all()
    return [serialize_conversation_summary(item) for item in conversations]


@router.post("/conversations", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate,
    request: Request,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> ConversationRead:
    store = await get_store_or_404(session, payload.store_id)
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loja nao encontrada.")
    if not actor.has_permission("crm.manage", company_id=store.company_id, store_id=store.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para abrir conversas.")

    channel = await session.scalar(select(WhatsAppChannel).where(WhatsAppChannel.id == payload.channel_id))
    if not channel or channel.store_id != store.id or channel.company_id != store.company_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Canal invalido para esta loja.")

    contact = await _load_contact(session, payload.contact_id)
    if not contact or contact.company_id != store.company_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Contato invalido para esta loja.")

    try:
        conversation_status = ConversationStatus(payload.status)
        priority = ConversationPriority(payload.priority)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Status ou prioridade invalidos.") from exc

    assigned_user = None
    if payload.assigned_user_id:
        assigned_user = await session.get(PlatformUser, payload.assigned_user_id)
        if not assigned_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario responsavel nao encontrado.")
        can_access = await ensure_user_can_access_store(
            session,
            user_id=assigned_user.id,
            store_id=store.id,
            company_id=store.company_id,
        )
        if not can_access:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Usuario escolhido nao tem acesso a esta loja.",
            )

    tags: list[Tag] = []
    for tag_id in payload.tag_ids:
        tag = await _load_tag(session, tag_id)
        if not tag:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tag {tag_id} nao encontrada.")
        _ensure_tag_scope(tag, company_id=store.company_id, store_id=store.id)
        tags.append(tag)

    conversation = Conversation(
        company_id=store.company_id,
        store_id=store.id,
        channel_id=channel.id,
        contact_id=contact.id,
        assigned_user_id=assigned_user.id if assigned_user else None,
        subject=payload.subject,
        status=conversation_status,
        priority=priority,
        source=payload.source,
        funnel_stage=payload.funnel_stage,
        closure_reason=payload.closure_reason,
        resolution_notes=payload.resolution_notes,
    )
    conversation.company = store.company
    conversation.store = store
    conversation.channel = channel
    conversation.contact = contact
    conversation.assigned_user = assigned_user
    conversation.tags = tags
    session.add(conversation)
    await session.flush()

    await append_conversation_event(
        session,
        conversation=conversation,
        event_type=ConversationEventType.OPENED,
        description="Conversa criada manualmente.",
        actor_user_id=actor.user.id,
        metadata={"channel_id": str(channel.id), "contact_id": str(contact.id)},
    )

    if assigned_user:
        session.add(
            ConversationAssignment(
                company_id=store.company_id,
                store_id=store.id,
                conversation_id=conversation.id,
                assigned_user_id=assigned_user.id,
                assigned_by_user_id=actor.user.id,
                reason="Atribuicao inicial da conversa.",
            )
        )
        await append_conversation_event(
            session,
            conversation=conversation,
            event_type=ConversationEventType.ASSIGNED,
            description=f"Conversa atribuida para {assigned_user.full_name}.",
            actor_user_id=actor.user.id,
            metadata={"assigned_user_id": str(assigned_user.id)},
        )

    await record_audit_log(
        session,
        action="crm.conversations.created",
        resource_type="conversation",
        actor_user_id=actor.user.id,
        resource_id=str(conversation.id),
        company_id=conversation.company_id,
        store_id=conversation.store_id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
    )
    automation_executions = await build_automation_executions_for_trigger(
        session,
        trigger_type=AutomationTriggerType.CONVERSATION_OPENED,
        conversation=conversation,
        requested_by_user_id=actor.user.id,
        metadata={"origin": "crm.create_conversation"},
    )
    if assigned_user:
        automation_executions.extend(
            await build_automation_executions_for_trigger(
                session,
                trigger_type=AutomationTriggerType.CONVERSATION_ASSIGNED,
                conversation=conversation,
                requested_by_user_id=actor.user.id,
                metadata={
                    "origin": "crm.create_conversation",
                    "assigned_user_id": str(assigned_user.id),
                    "reason": "initial_assignment",
                },
            )
        )
    await session.commit()
    _dispatch_automation_executions(automation_executions)
    conversation = await _load_conversation(session, conversation.id, detailed=True)
    return serialize_conversation(conversation)


@router.get("/conversations/{conversation_id}", response_model=ConversationRead)
async def get_conversation(
    conversation_id: UUID,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> ConversationRead:
    conversation = await _load_conversation(session, conversation_id, detailed=True)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa nao encontrada.")
    if not actor.has_permission("crm.view", company_id=conversation.company_id, store_id=conversation.store_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem acesso a esta conversa.")
    return serialize_conversation(conversation)


@router.patch("/conversations/{conversation_id}", response_model=ConversationRead)
async def update_conversation(
    conversation_id: UUID,
    payload: ConversationUpdate,
    request: Request,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> ConversationRead:
    conversation = await _load_conversation(session, conversation_id, detailed=True)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa nao encontrada.")
    if not actor.has_permission("crm.manage", company_id=conversation.company_id, store_id=conversation.store_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para alterar a conversa.")

    changed_fields = payload.model_dump(exclude_unset=True)
    priority_value = changed_fields.pop("priority", None)
    if priority_value is not None:
        try:
            conversation.priority = ConversationPriority(priority_value)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Prioridade invalida.") from exc

    for field, value in changed_fields.items():
        if value is None:
            continue
        setattr(conversation, field, value)

    if payload.model_dump(exclude_unset=True):
        await append_conversation_event(
            session,
            conversation=conversation,
            event_type=ConversationEventType.UPDATED,
            description="Dados gerais da conversa foram atualizados.",
            actor_user_id=actor.user.id,
            metadata={"fields": sorted(payload.model_dump(exclude_unset=True).keys())},
        )

    await record_audit_log(
        session,
        action="crm.conversations.updated",
        resource_type="conversation",
        actor_user_id=actor.user.id,
        resource_id=str(conversation.id),
        company_id=conversation.company_id,
        store_id=conversation.store_id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"fields": sorted(payload.model_dump(exclude_unset=True).keys())},
    )
    await session.commit()
    conversation = await _load_conversation(session, conversation.id, detailed=True)
    return serialize_conversation(conversation)


@router.post("/conversations/{conversation_id}/assign", response_model=ConversationRead)
async def assign_conversation(
    conversation_id: UUID,
    payload: ConversationAssign,
    request: Request,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> ConversationRead:
    conversation = await _load_conversation(session, conversation_id, detailed=True)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa nao encontrada.")
    if not actor.has_permission(
        "conversations.assign",
        company_id=conversation.company_id,
        store_id=conversation.store_id,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para redistribuir conversas.")

    now = datetime.now(timezone.utc)
    release_open_assignment(conversation, now)

    if payload.assigned_user_id is None:
        conversation.assigned_user_id = None
        conversation.assigned_user = None
        await append_conversation_event(
            session,
            conversation=conversation,
            event_type=ConversationEventType.UNASSIGNED,
            description="Conversa devolvida para fila.",
            actor_user_id=actor.user.id,
            metadata={"reason": payload.reason},
        )
        audit_action = "crm.conversations.unassigned"
        automation_executions = []
    else:
        assigned_user = await session.get(PlatformUser, payload.assigned_user_id)
        if not assigned_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario responsavel nao encontrado.")
        can_access = await ensure_user_can_access_store(
            session,
            user_id=assigned_user.id,
            store_id=conversation.store_id,
            company_id=conversation.company_id,
        )
        if not can_access:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Usuario escolhido nao tem acesso a esta loja.",
            )
        conversation.assigned_user_id = assigned_user.id
        conversation.assigned_user = assigned_user
        session.add(
            ConversationAssignment(
                company_id=conversation.company_id,
                store_id=conversation.store_id,
                conversation_id=conversation.id,
                assigned_user_id=assigned_user.id,
                assigned_by_user_id=actor.user.id,
                reason=payload.reason,
                assigned_at=now,
            )
        )
        await append_conversation_event(
            session,
            conversation=conversation,
            event_type=ConversationEventType.ASSIGNED,
            description=f"Conversa atribuida para {assigned_user.full_name}.",
            actor_user_id=actor.user.id,
            metadata={"assigned_user_id": str(assigned_user.id), "reason": payload.reason},
        )
        audit_action = "crm.conversations.assigned"
        automation_executions = await build_automation_executions_for_trigger(
            session,
            trigger_type=AutomationTriggerType.CONVERSATION_ASSIGNED,
            conversation=conversation,
            requested_by_user_id=actor.user.id,
            metadata={
                "origin": "crm.assign_conversation",
                "assigned_user_id": str(assigned_user.id),
                "reason": payload.reason,
            },
        )

    await record_audit_log(
        session,
        action=audit_action,
        resource_type="conversation",
        actor_user_id=actor.user.id,
        resource_id=str(conversation.id),
        company_id=conversation.company_id,
        store_id=conversation.store_id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"assigned_user_id": str(payload.assigned_user_id) if payload.assigned_user_id else None},
    )
    await session.commit()
    _dispatch_automation_executions(automation_executions)
    conversation = await _load_conversation(session, conversation.id, detailed=True)
    return serialize_conversation(conversation)


@router.post("/conversations/{conversation_id}/status", response_model=ConversationRead)
async def update_conversation_status(
    conversation_id: UUID,
    payload: ConversationStatusUpdate,
    request: Request,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> ConversationRead:
    conversation = await _load_conversation(session, conversation_id, detailed=True)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa nao encontrada.")
    if not actor.has_permission("crm.manage", company_id=conversation.company_id, store_id=conversation.store_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para alterar o status.")

    try:
        new_status = ConversationStatus(payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Status da conversa invalido.") from exc

    previous_status = conversation.status
    conversation.status = new_status
    if payload.resolution_notes is not None:
        conversation.resolution_notes = payload.resolution_notes

    if new_status in {ConversationStatus.CLOSED, ConversationStatus.LOST, ConversationStatus.CANCELED}:
        conversation.closed_at = conversation.closed_at or datetime.now(timezone.utc)
        if payload.reason:
            conversation.closure_reason = payload.reason
    else:
        conversation.closed_at = None
        if payload.reason:
            conversation.closure_reason = payload.reason

    await append_conversation_event(
        session,
        conversation=conversation,
        event_type=ConversationEventType.STATUS_CHANGED,
        description=f"Status alterado de {previous_status.value} para {new_status.value}.",
        actor_user_id=actor.user.id,
        metadata={"from": previous_status.value, "to": new_status.value, "reason": payload.reason},
    )
    await record_audit_log(
        session,
        action="crm.conversations.status_changed",
        resource_type="conversation",
        actor_user_id=actor.user.id,
        resource_id=str(conversation.id),
        company_id=conversation.company_id,
        store_id=conversation.store_id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"from": previous_status.value, "to": new_status.value},
    )
    await session.commit()
    conversation = await _load_conversation(session, conversation.id, detailed=True)
    return serialize_conversation(conversation)


@router.post("/conversations/{conversation_id}/messages", response_model=ConversationMessageRead, status_code=status.HTTP_201_CREATED)
async def create_conversation_message(
    conversation_id: UUID,
    payload: ConversationMessageCreate,
    request: Request,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> ConversationMessageRead:
    conversation = await _load_conversation(session, conversation_id, detailed=True)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa nao encontrada.")
    if not actor.has_permission("crm.manage", company_id=conversation.company_id, store_id=conversation.store_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para registrar mensagens.")

    try:
        direction = MessageDirection(payload.direction)
        message_type = MessageType(payload.message_type)
        delivery_status = MessageDeliveryStatus(payload.delivery_status)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mensagem invalida.") from exc

    if payload.sender_type:
        try:
            sender_type = MessageSenderType(payload.sender_type)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Remetente invalido.") from exc
    else:
        sender_type = MessageSenderType.CUSTOMER if direction == MessageDirection.INBOUND else MessageSenderType.AGENT

    is_human = direction == MessageDirection.OUTBOUND and sender_type == MessageSenderType.AGENT
    message = ConversationMessage(
        company_id=conversation.company_id,
        store_id=conversation.store_id,
        channel_id=conversation.channel_id,
        conversation_id=conversation.id,
        author_user_id=actor.user.id if direction == MessageDirection.OUTBOUND else None,
        direction=direction,
        sender_type=sender_type,
        message_type=message_type,
        delivery_status=delivery_status,
        provider_message_id=payload.provider_message_id,
        text_body=payload.text_body,
        is_human=is_human,
        metadata_json=payload.metadata,
    )
    message.conversation = conversation
    message.channel = conversation.channel
    if direction == MessageDirection.OUTBOUND:
        message.author_user = actor.user
    session.add(message)
    await session.flush()

    touch_conversation_after_message(conversation, message)
    await append_conversation_event(
        session,
        conversation=conversation,
        event_type=ConversationEventType.MESSAGE_LOGGED,
        description="Mensagem registrada na timeline.",
        actor_user_id=actor.user.id if direction == MessageDirection.OUTBOUND else None,
        metadata={"message_id": str(message.id), "direction": direction.value},
    )
    await record_audit_log(
        session,
        action="crm.messages.logged",
        resource_type="conversation_message",
        actor_user_id=actor.user.id if direction == MessageDirection.OUTBOUND else None,
        resource_id=str(message.id),
        company_id=conversation.company_id,
        store_id=conversation.store_id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"conversation_id": str(conversation.id), "direction": direction.value},
    )
    await session.commit()
    return serialize_message(message)


@router.post("/conversations/{conversation_id}/notes", response_model=ConversationEventRead, status_code=status.HTTP_201_CREATED)
async def add_conversation_note(
    conversation_id: UUID,
    payload: ConversationNoteCreate,
    request: Request,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> ConversationEventRead:
    conversation = await _load_conversation(session, conversation_id, detailed=True)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa nao encontrada.")
    if not actor.has_permission("crm.manage", company_id=conversation.company_id, store_id=conversation.store_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para adicionar notas.")

    event = await append_conversation_event(
        session,
        conversation=conversation,
        event_type=ConversationEventType.NOTE_ADDED,
        description=payload.note,
        actor_user_id=actor.user.id,
    )
    await record_audit_log(
        session,
        action="crm.notes.created",
        resource_type="conversation_event",
        actor_user_id=actor.user.id,
        resource_id=str(event.id),
        company_id=conversation.company_id,
        store_id=conversation.store_id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"conversation_id": str(conversation.id)},
    )
    await session.commit()
    return serialize_event(event)


@router.post("/conversations/{conversation_id}/tags/{tag_id}", response_model=ConversationRead)
async def attach_tag_to_conversation(
    conversation_id: UUID,
    tag_id: UUID,
    request: Request,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> ConversationRead:
    conversation = await _load_conversation(session, conversation_id, detailed=True)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa nao encontrada.")
    if not actor.has_permission("crm.manage", company_id=conversation.company_id, store_id=conversation.store_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para etiquetar a conversa.")

    tag = await _load_tag(session, tag_id)
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag nao encontrada.")
    _ensure_tag_scope(tag, company_id=conversation.company_id, store_id=conversation.store_id)

    if tag not in conversation.tags:
        conversation.tags.append(tag)
        await append_conversation_event(
            session,
            conversation=conversation,
            event_type=ConversationEventType.TAG_ATTACHED,
            description=f"Tag '{tag.name}' vinculada a conversa.",
            actor_user_id=actor.user.id,
            metadata={"tag_id": str(tag.id)},
        )

    await record_audit_log(
        session,
        action="crm.conversations.tag_attached",
        resource_type="conversation",
        actor_user_id=actor.user.id,
        resource_id=str(conversation.id),
        company_id=conversation.company_id,
        store_id=conversation.store_id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"tag_id": str(tag.id)},
    )
    await session.commit()
    conversation = await _load_conversation(session, conversation.id, detailed=True)
    return serialize_conversation(conversation)


@router.delete("/conversations/{conversation_id}/tags/{tag_id}", response_model=ConversationRead)
async def remove_tag_from_conversation(
    conversation_id: UUID,
    tag_id: UUID,
    request: Request,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> ConversationRead:
    conversation = await _load_conversation(session, conversation_id, detailed=True)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa nao encontrada.")
    if not actor.has_permission("crm.manage", company_id=conversation.company_id, store_id=conversation.store_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para etiquetar a conversa.")

    tag = await _load_tag(session, tag_id)
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag nao encontrada.")

    conversation.tags = [item for item in conversation.tags if item.id != tag.id]
    await append_conversation_event(
        session,
        conversation=conversation,
        event_type=ConversationEventType.TAG_REMOVED,
        description=f"Tag '{tag.name}' removida da conversa.",
        actor_user_id=actor.user.id,
        metadata={"tag_id": str(tag.id)},
    )
    await record_audit_log(
        session,
        action="crm.conversations.tag_removed",
        resource_type="conversation",
        actor_user_id=actor.user.id,
        resource_id=str(conversation.id),
        company_id=conversation.company_id,
        store_id=conversation.store_id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"tag_id": str(tag.id)},
    )
    await session.commit()
    conversation = await _load_conversation(session, conversation.id, detailed=True)
    return serialize_conversation(conversation)


@router.delete("/conversations/{conversation_id}", response_model=MessageResponse)
async def archive_conversation(
    conversation_id: UUID,
    request: Request,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    conversation = await _load_conversation(session, conversation_id, detailed=True)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa nao encontrada.")
    if not actor.has_permission("crm.manage", company_id=conversation.company_id, store_id=conversation.store_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para encerrar esta conversa.")

    previous_status = conversation.status
    conversation.status = ConversationStatus.CLOSED
    conversation.closed_at = conversation.closed_at or datetime.now(timezone.utc)
    release_open_assignment(conversation, conversation.closed_at)
    await append_conversation_event(
        session,
        conversation=conversation,
        event_type=ConversationEventType.STATUS_CHANGED,
        description=f"Conversa encerrada a partir de {previous_status.value}.",
        actor_user_id=actor.user.id,
        metadata={"from": previous_status.value, "to": ConversationStatus.CLOSED.value},
    )
    await record_audit_log(
        session,
        action="crm.conversations.closed",
        resource_type="conversation",
        actor_user_id=actor.user.id,
        resource_id=str(conversation.id),
        company_id=conversation.company_id,
        store_id=conversation.store_id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
    )
    await session.commit()
    return MessageResponse(message="Conversa encerrada.")
