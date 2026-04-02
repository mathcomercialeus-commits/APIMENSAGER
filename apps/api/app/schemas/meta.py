from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import APIModel


class ChannelCredentialUpsert(APIModel):
    app_id: str = ""
    business_account_id: str = ""
    phone_number_id: str = Field(min_length=1, max_length=120)
    graph_api_version: str = "v21.0"
    webhook_callback_url: str = ""
    access_token: str | None = None
    app_secret: str | None = None
    webhook_verify_token: str | None = None
    is_active: bool = True


class ChannelCredentialRead(APIModel):
    id: UUID
    channel_id: UUID
    phone_number_id: str
    app_id: str
    business_account_id: str
    graph_api_version: str
    webhook_callback_url: str
    verify_token_hint: str
    access_token_last4: str
    has_access_token: bool
    has_app_secret: bool
    has_webhook_verify_token: bool
    is_active: bool
    status_payload: dict
    last_healthcheck_at: datetime | None
    last_error_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MessageTemplateRead(APIModel):
    id: UUID
    meta_template_id: str
    name: str
    language_code: str
    category: str
    status: str
    components_schema: dict
    last_synced_at: datetime | None


class TemplatesSyncResponse(APIModel):
    synced_count: int
    templates: list[MessageTemplateRead]


class SendTextMessageRequest(APIModel):
    body: str = Field(min_length=1, max_length=4096)
    preview_url: bool = False


class SendTemplateMessageRequest(APIModel):
    template_name: str = Field(min_length=1, max_length=160)
    language_code: str = Field(min_length=2, max_length=16)
    components: list[dict] = Field(default_factory=list)


class OutboundMessageResponse(APIModel):
    conversation_id: UUID
    conversation_message_id: UUID
    channel_id: UUID
    provider_message_id: str | None
    delivery_status: str
    inside_customer_service_window: bool
    provider_response: dict
    sent_at: datetime


class WebhookAck(APIModel):
    message: str
    event_id: UUID | None = None
    processing_status: str | None = None
