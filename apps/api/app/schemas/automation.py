from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import APIModel


class AutomationRuleCreate(APIModel):
    store_id: UUID
    channel_id: UUID | None = None
    name: str = Field(min_length=3, max_length=160)
    description: str = ""
    trigger_type: str = "manual"
    action_type: str
    is_active: bool = True
    priority: int = Field(default=100, ge=1, le=1000)
    respect_customer_window: bool = True
    message_body: str = ""
    template_name: str = ""
    template_language_code: str = ""
    settings: dict = Field(default_factory=dict)


class AutomationRuleUpdate(APIModel):
    channel_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    trigger_type: str | None = None
    action_type: str | None = None
    is_active: bool | None = None
    priority: int | None = Field(default=None, ge=1, le=1000)
    respect_customer_window: bool | None = None
    message_body: str | None = None
    template_name: str | None = None
    template_language_code: str | None = None
    settings: dict | None = None


class AutomationRuleRead(APIModel):
    id: UUID
    company_id: UUID
    company_name: str
    store_id: UUID
    store_name: str
    channel_id: UUID | None
    channel_name: str | None
    name: str
    description: str
    trigger_type: str
    action_type: str
    is_active: bool
    priority: int
    respect_customer_window: bool
    message_body: str
    template_name: str
    template_language_code: str
    settings: dict
    last_executed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AutomationExecuteRequest(APIModel):
    conversation_id: UUID
    metadata: dict = Field(default_factory=dict)


class AutomationExecutionRead(APIModel):
    id: UUID
    rule_id: UUID
    company_id: UUID
    store_id: UUID
    channel_id: UUID | None
    conversation_id: UUID | None
    requested_by_user_id: UUID | None
    requested_by_user_name: str | None
    status: str
    rendered_message: str
    result_notes: str
    provider_message_id: str
    provider_response: dict
    metadata: dict
    processing_attempts: int
    last_attempt_at: datetime | None
    next_retry_at: datetime | None
    dead_lettered_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime
