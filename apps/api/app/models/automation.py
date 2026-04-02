from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import AutomationActionType, AutomationExecutionStatus, AutomationTriggerType


class AutomationRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "automation_rules"
    __table_args__ = (UniqueConstraint("store_id", "name"),)

    company_id: Mapped[PGUUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("client_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    store_id: Mapped[PGUUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    channel_id: Mapped[PGUUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("whatsapp_channels.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    trigger_type: Mapped[AutomationTriggerType] = mapped_column(Enum(AutomationTriggerType, native_enum=False), default=AutomationTriggerType.MANUAL, nullable=False)
    action_type: Mapped[AutomationActionType] = mapped_column(Enum(AutomationActionType, native_enum=False), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    respect_customer_window: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    message_body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    template_name: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    template_language_code: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    settings_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    last_executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    company = relationship("ClientCompany", lazy="joined")
    store = relationship("Store", lazy="joined")
    channel = relationship("WhatsAppChannel", lazy="joined")
    executions = relationship("AutomationExecution", back_populates="rule", cascade="all, delete-orphan", lazy="selectin")


class AutomationExecution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "automation_executions"

    rule_id: Mapped[PGUUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("automation_rules.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id: Mapped[PGUUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("client_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    store_id: Mapped[PGUUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    channel_id: Mapped[PGUUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("whatsapp_channels.id", ondelete="SET NULL"), nullable=True, index=True)
    conversation_id: Mapped[PGUUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True)
    requested_by_user_id: Mapped[PGUUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("platform_users.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[AutomationExecutionStatus] = mapped_column(Enum(AutomationExecutionStatus, native_enum=False), default=AutomationExecutionStatus.QUEUED, nullable=False, index=True)
    rendered_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    result_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    provider_message_id: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    provider_response: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    processing_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dead_lettered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    rule = relationship("AutomationRule", back_populates="executions", lazy="joined")
    company = relationship("ClientCompany", lazy="joined")
    store = relationship("Store", lazy="joined")
    channel = relationship("WhatsAppChannel", lazy="joined")
    conversation = relationship("Conversation", lazy="joined")
    requested_by_user = relationship("PlatformUser", lazy="joined")
