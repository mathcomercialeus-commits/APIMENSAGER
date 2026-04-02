from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from app.schemas.common import APIModel


class UserCompactRead(APIModel):
    id: UUID
    full_name: str
    login: str


class TagCreate(APIModel):
    company_id: UUID
    store_id: UUID | None = None
    name: str
    color_hex: str = "#2563EB"


class TagRead(APIModel):
    id: UUID
    company_id: UUID
    store_id: UUID | None
    name: str
    color_hex: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class WhatsAppChannelCreate(APIModel):
    company_id: UUID
    store_id: UUID
    name: str
    code: str
    display_phone_number: str
    phone_number_e164: str
    external_phone_number_id: str | None = None
    description: str = ""
    color_hex: str = "#16A34A"
    is_default: bool = False
    support_notes: str = ""


class WhatsAppChannelUpdate(APIModel):
    name: str | None = None
    display_phone_number: str | None = None
    phone_number_e164: str | None = None
    external_phone_number_id: str | None = None
    description: str | None = None
    color_hex: str | None = None
    is_default: bool | None = None
    status: str | None = None
    support_notes: str | None = None


class WhatsAppChannelRead(APIModel):
    id: UUID
    company_id: UUID
    company_name: str
    store_id: UUID
    store_name: str
    name: str
    code: str
    provider: str
    status: str
    display_phone_number: str
    phone_number_e164: str
    external_phone_number_id: str | None
    description: str
    color_hex: str
    is_default: bool
    support_notes: str
    created_at: datetime
    updated_at: datetime


class ContactCreate(APIModel):
    company_id: UUID
    primary_store_id: UUID | None = None
    full_name: str
    phone_number_e164: str
    alternate_phone: str | None = None
    email: str | None = None
    document_number: str | None = None
    source: str = ""
    notes: str = ""
    status: str = "active"
    tag_ids: list[UUID] = Field(default_factory=list)


class ContactUpdate(APIModel):
    primary_store_id: UUID | None = None
    full_name: str | None = None
    phone_number_e164: str | None = None
    alternate_phone: str | None = None
    email: str | None = None
    document_number: str | None = None
    source: str | None = None
    notes: str | None = None
    status: str | None = None


class ContactRead(APIModel):
    id: UUID
    company_id: UUID
    primary_store_id: UUID | None
    primary_store_name: str | None
    full_name: str
    phone_number_e164: str
    alternate_phone: str | None
    email: str | None
    document_number: str | None
    source: str
    notes: str
    status: str
    last_interaction_at: datetime | None
    tags: list[TagRead]
    created_at: datetime
    updated_at: datetime


class ConversationCreate(APIModel):
    store_id: UUID
    channel_id: UUID
    contact_id: UUID
    subject: str = ""
    status: str = "new"
    priority: str = "normal"
    source: str = "whatsapp"
    funnel_stage: str = ""
    assigned_user_id: UUID | None = None
    closure_reason: str = ""
    resolution_notes: str = ""
    tag_ids: list[UUID] = Field(default_factory=list)


class ConversationUpdate(APIModel):
    subject: str | None = None
    priority: str | None = None
    funnel_stage: str | None = None
    closure_reason: str | None = None
    resolution_notes: str | None = None


class ConversationAssign(APIModel):
    assigned_user_id: UUID | None = None
    reason: str = ""


class ConversationStatusUpdate(APIModel):
    status: str
    reason: str = ""
    resolution_notes: str | None = None


class ConversationMessageCreate(APIModel):
    direction: str
    text_body: str
    message_type: str = "text"
    sender_type: str | None = None
    provider_message_id: str | None = None
    delivery_status: str = "sent"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationNoteCreate(APIModel):
    note: str


class ConversationMessageRead(APIModel):
    id: UUID
    conversation_id: UUID
    author_user: UserCompactRead | None
    direction: str
    sender_type: str
    message_type: str
    delivery_status: str
    provider_message_id: str | None
    text_body: str
    is_human: bool
    sent_at: datetime
    delivered_at: datetime | None
    read_at: datetime | None
    failed_at: datetime | None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ConversationEventRead(APIModel):
    id: UUID
    conversation_id: UUID
    actor_user: UserCompactRead | None
    event_type: str
    description: str
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ConversationAssignmentRead(APIModel):
    id: UUID
    conversation_id: UUID
    assigned_user: UserCompactRead
    assigned_by_user: UserCompactRead | None
    reason: str
    assigned_at: datetime
    released_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ConversationSummaryRead(APIModel):
    id: UUID
    company_id: UUID
    company_name: str
    store_id: UUID
    store_name: str
    channel: WhatsAppChannelRead
    contact_id: UUID
    contact_name: str
    contact_phone_number_e164: str
    assigned_user: UserCompactRead | None
    status: str
    priority: str
    source: str
    subject: str
    funnel_stage: str
    opened_at: datetime
    first_customer_message_at: datetime | None
    last_customer_message_at: datetime | None
    first_human_response_at: datetime | None
    last_message_at: datetime | None
    closed_at: datetime | None
    closure_reason: str
    resolution_notes: str
    first_response_seconds: int | None
    active_duration_seconds: int | None
    resolution_seconds: int | None
    tags: list[TagRead]
    created_at: datetime
    updated_at: datetime


class ConversationRead(ConversationSummaryRead):
    contact: ContactRead
    messages: list[ConversationMessageRead]
    events: list[ConversationEventRead]
    assignments: list[ConversationAssignmentRead]
