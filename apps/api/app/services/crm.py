from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.crm import (
    Contact,
    Conversation,
    ConversationAssignment,
    ConversationEvent,
    ConversationMessage,
    Tag,
    WhatsAppChannel,
)
from app.models.enums import ConversationEventType, ConversationStatus, MessageDirection
from app.schemas.crm import (
    ContactRead,
    ConversationAssignmentRead,
    ConversationEventRead,
    ConversationMessageRead,
    ConversationRead,
    ConversationSummaryRead,
    TagRead,
    UserCompactRead,
    WhatsAppChannelRead,
)
from app.services.access import load_user_with_access


def channel_query_options():
    return ()


def tag_query_options():
    return ()


def contact_query_options():
    return (
        selectinload(Contact.tags),
        selectinload(Contact.primary_store),
    )


def conversation_query_options():
    return (
        selectinload(Conversation.tags),
        selectinload(Conversation.channel),
        selectinload(Conversation.contact).selectinload(Contact.tags),
        selectinload(Conversation.contact).selectinload(Contact.primary_store),
        selectinload(Conversation.assigned_user),
        selectinload(Conversation.store),
        selectinload(Conversation.company),
    )


def conversation_detail_query_options():
    return (
        *conversation_query_options(),
        selectinload(Conversation.messages).selectinload(ConversationMessage.author_user),
        selectinload(Conversation.events).selectinload(ConversationEvent.actor),
        selectinload(Conversation.assignments).selectinload(ConversationAssignment.assigned_user),
        selectinload(Conversation.assignments).selectinload(ConversationAssignment.assigned_by_user),
    )


def serialize_user_compact(user) -> UserCompactRead | None:
    if not user:
        return None
    return UserCompactRead(id=user.id, full_name=user.full_name, login=user.login)


def serialize_tag(tag: Tag) -> TagRead:
    return TagRead(
        id=tag.id,
        company_id=tag.company_id,
        store_id=tag.store_id,
        name=tag.name,
        color_hex=tag.color_hex,
        is_active=tag.is_active,
        created_at=tag.created_at,
        updated_at=tag.updated_at,
    )


def serialize_channel(channel: WhatsAppChannel) -> WhatsAppChannelRead:
    return WhatsAppChannelRead(
        id=channel.id,
        company_id=channel.company_id,
        company_name=channel.company.display_name,
        store_id=channel.store_id,
        store_name=channel.store.name,
        name=channel.name,
        code=channel.code,
        provider=channel.provider.value,
        status=channel.status.value,
        display_phone_number=channel.display_phone_number,
        phone_number_e164=channel.phone_number_e164,
        external_phone_number_id=channel.external_phone_number_id,
        description=channel.description,
        color_hex=channel.color_hex,
        is_default=channel.is_default,
        support_notes=channel.support_notes,
        created_at=channel.created_at,
        updated_at=channel.updated_at,
    )


def serialize_contact(contact: Contact) -> ContactRead:
    return ContactRead(
        id=contact.id,
        company_id=contact.company_id,
        primary_store_id=contact.primary_store_id,
        primary_store_name=contact.primary_store.name if contact.primary_store else None,
        full_name=contact.full_name,
        phone_number_e164=contact.phone_number_e164,
        alternate_phone=contact.alternate_phone,
        email=contact.email,
        document_number=contact.document_number,
        source=contact.source,
        notes=contact.notes,
        status=contact.status.value,
        last_interaction_at=contact.last_interaction_at,
        tags=[serialize_tag(tag) for tag in sorted(contact.tags, key=lambda item: item.name.lower())],
        created_at=contact.created_at,
        updated_at=contact.updated_at,
    )


def serialize_message(message: ConversationMessage) -> ConversationMessageRead:
    return ConversationMessageRead(
        id=message.id,
        conversation_id=message.conversation_id,
        author_user=serialize_user_compact(message.author_user),
        direction=message.direction.value,
        sender_type=message.sender_type.value,
        message_type=message.message_type.value,
        delivery_status=message.delivery_status.value,
        provider_message_id=message.provider_message_id,
        text_body=message.text_body,
        is_human=message.is_human,
        sent_at=message.sent_at,
        delivered_at=message.delivered_at,
        read_at=message.read_at,
        failed_at=message.failed_at,
        metadata=message.metadata_json,
        created_at=message.created_at,
        updated_at=message.updated_at,
    )


def serialize_event(event: ConversationEvent) -> ConversationEventRead:
    return ConversationEventRead(
        id=event.id,
        conversation_id=event.conversation_id,
        actor_user=serialize_user_compact(event.actor),
        event_type=event.event_type.value,
        description=event.description,
        metadata=event.metadata_json,
        created_at=event.created_at,
        updated_at=event.updated_at,
    )


def serialize_assignment(assignment: ConversationAssignment) -> ConversationAssignmentRead:
    return ConversationAssignmentRead(
        id=assignment.id,
        conversation_id=assignment.conversation_id,
        assigned_user=serialize_user_compact(assignment.assigned_user),
        assigned_by_user=serialize_user_compact(assignment.assigned_by_user),
        reason=assignment.reason,
        assigned_at=assignment.assigned_at,
        released_at=assignment.released_at,
        created_at=assignment.created_at,
        updated_at=assignment.updated_at,
    )


def first_response_seconds(conversation: Conversation) -> int | None:
    if not conversation.first_human_response_at:
        return None
    reference = conversation.first_customer_message_at or conversation.opened_at
    return max(0, int((conversation.first_human_response_at - reference).total_seconds()))


def active_duration_seconds(conversation: Conversation) -> int | None:
    if not conversation.opened_at:
        return None
    end_time = conversation.closed_at or conversation.last_message_at or datetime.now(timezone.utc)
    return max(0, int((end_time - conversation.opened_at).total_seconds()))


def resolution_seconds(conversation: Conversation) -> int | None:
    if not conversation.closed_at:
        return None
    return max(0, int((conversation.closed_at - conversation.opened_at).total_seconds()))


def serialize_conversation_summary(conversation: Conversation) -> ConversationSummaryRead:
    return ConversationSummaryRead(
        id=conversation.id,
        company_id=conversation.company_id,
        company_name=conversation.company.display_name,
        store_id=conversation.store_id,
        store_name=conversation.store.name,
        channel=serialize_channel(conversation.channel),
        contact_id=conversation.contact_id,
        contact_name=conversation.contact.full_name,
        contact_phone_number_e164=conversation.contact.phone_number_e164,
        assigned_user=serialize_user_compact(conversation.assigned_user),
        status=conversation.status.value,
        priority=conversation.priority.value,
        source=conversation.source,
        subject=conversation.subject,
        funnel_stage=conversation.funnel_stage,
        opened_at=conversation.opened_at,
        first_customer_message_at=conversation.first_customer_message_at,
        last_customer_message_at=conversation.last_customer_message_at,
        first_human_response_at=conversation.first_human_response_at,
        last_message_at=conversation.last_message_at,
        closed_at=conversation.closed_at,
        closure_reason=conversation.closure_reason,
        resolution_notes=conversation.resolution_notes,
        first_response_seconds=first_response_seconds(conversation),
        active_duration_seconds=active_duration_seconds(conversation),
        resolution_seconds=resolution_seconds(conversation),
        tags=[serialize_tag(tag) for tag in sorted(conversation.tags, key=lambda item: item.name.lower())],
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def serialize_conversation(conversation: Conversation) -> ConversationRead:
    return ConversationRead(
        **serialize_conversation_summary(conversation).model_dump(),
        contact=serialize_contact(conversation.contact),
        messages=[
            serialize_message(message)
            for message in sorted(conversation.messages, key=lambda item: (item.sent_at, item.created_at))
        ],
        events=[
            serialize_event(event)
            for event in sorted(conversation.events, key=lambda item: (item.created_at, item.id))
        ],
        assignments=[
            serialize_assignment(item)
            for item in sorted(conversation.assignments, key=lambda entry: (entry.assigned_at, entry.created_at))
        ],
    )


async def append_conversation_event(
    session: AsyncSession,
    *,
    conversation: Conversation,
    event_type: ConversationEventType,
    description: str,
    actor_user_id: UUID | None = None,
    metadata: dict | None = None,
) -> ConversationEvent:
    event = ConversationEvent(
        company_id=conversation.company_id,
        store_id=conversation.store_id,
        conversation_id=conversation.id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        description=description,
        metadata_json=metadata or {},
    )
    session.add(event)
    await session.flush()
    return event


def get_open_assignment(conversation: Conversation) -> ConversationAssignment | None:
    open_assignments = [item for item in conversation.assignments if item.released_at is None]
    if not open_assignments:
        return None
    open_assignments.sort(key=lambda item: (item.assigned_at, item.created_at), reverse=True)
    return open_assignments[0]


def release_open_assignment(conversation: Conversation, released_at: datetime | None = None) -> None:
    current_assignment = get_open_assignment(conversation)
    if current_assignment and current_assignment.released_at is None:
        current_assignment.released_at = released_at or datetime.now(timezone.utc)


def touch_conversation_after_message(conversation: Conversation, message: ConversationMessage) -> None:
    reference_time = message.sent_at
    conversation.last_message_at = reference_time
    conversation.contact.last_interaction_at = reference_time

    if message.direction == MessageDirection.INBOUND:
        if conversation.first_customer_message_at is None:
            conversation.first_customer_message_at = reference_time
        conversation.last_customer_message_at = reference_time
    else:
        if message.is_human and conversation.first_human_response_at is None:
            conversation.first_human_response_at = reference_time
        if message.is_human and conversation.status in {
            ConversationStatus.NEW,
            ConversationStatus.QUEUED,
            ConversationStatus.AWAITING_CUSTOMER,
        }:
            conversation.status = ConversationStatus.IN_PROGRESS


async def ensure_user_can_access_store(
    session: AsyncSession,
    *,
    user_id: UUID,
    store_id: UUID,
    company_id: UUID,
) -> bool:
    user = await load_user_with_access(session, user_id)
    if not user:
        return False
    has_store_access = any(item.store_id == store_id and item.is_active for item in user.store_memberships)
    has_company_access = any(item.company_id == company_id and item.is_active for item in user.company_memberships)
    return has_store_access or has_company_access
