from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    PrimaryKeyConstraint,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


channel_templates = Table(
    "channel_templates",
    Base.metadata,
    Column(
        "channel_id",
        PGUUID(as_uuid=True),
        ForeignKey("whatsapp_channels.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "template_id",
        PGUUID(as_uuid=True),
        ForeignKey("message_templates.id", ondelete="CASCADE"),
        nullable=False,
    ),
    PrimaryKeyConstraint("channel_id", "template_id"),
)


class ChannelCredential(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "channel_credentials"

    channel_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("whatsapp_channels.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    app_id: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    business_account_id: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    graph_api_version: Mapped[str] = mapped_column(String(16), default="v21.0", nullable=False)
    webhook_callback_url: Mapped[str] = mapped_column(Text, default="", nullable=False)
    verify_token_hint: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    access_token_last4: Mapped[str] = mapped_column(String(8), default="", nullable=False)
    encrypted_access_token: Mapped[str] = mapped_column(Text, default="", nullable=False)
    encrypted_app_secret: Mapped[str] = mapped_column(Text, default="", nullable=False)
    encrypted_webhook_verify_token: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    last_healthcheck_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    channel = relationship("WhatsAppChannel", lazy="joined")


class MessageTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "message_templates"
    __table_args__ = (UniqueConstraint("name", "language_code"),)

    meta_template_id: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    language_code: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="UNKNOWN", nullable=False)
    components_schema: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    channels = relationship("WhatsAppChannel", secondary=channel_templates, lazy="selectin")


class WebhookEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "webhook_events"

    channel_id: Mapped[PGUUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("whatsapp_channels.id", ondelete="SET NULL"),
        nullable=True,
    )
    phone_number_id: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    headers: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    signature_valid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    processing_status: Mapped[str] = mapped_column(String(40), default="received", nullable=False)
    processing_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    processing_attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dead_lettered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    channel = relationship("WhatsAppChannel", lazy="joined")
