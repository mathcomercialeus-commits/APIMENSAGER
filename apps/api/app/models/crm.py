from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    ChannelProvider,
    ChannelStatus,
    ContactStatus,
    ConversationEventType,
    ConversationPriority,
    ConversationStatus,
    MessageDeliveryStatus,
    MessageDirection,
    MessageSenderType,
    MessageType,
)


contact_tags = Table(
    "contact_tags",
    Base.metadata,
    Column("contact_id", PGUUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", PGUUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


conversation_tags = Table(
    "conversation_tags",
    Base.metadata,
    Column(
        "conversation_id",
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("tag_id", PGUUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class WhatsAppChannel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "whatsapp_channels"
    __table_args__ = (
        UniqueConstraint("company_id", "code"),
        UniqueConstraint("company_id", "phone_number_e164"),
        UniqueConstraint("provider", "external_phone_number_id"),
    )

    company_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("client_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    store_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    provider: Mapped[ChannelProvider] = mapped_column(
        Enum(ChannelProvider, native_enum=False),
        default=ChannelProvider.META_CLOUD_API,
        nullable=False,
    )
    status: Mapped[ChannelStatus] = mapped_column(
        Enum(ChannelStatus, native_enum=False),
        default=ChannelStatus.ACTIVE,
        nullable=False,
    )
    display_phone_number: Mapped[str] = mapped_column(String(40), nullable=False)
    phone_number_e164: Mapped[str] = mapped_column(String(32), nullable=False)
    external_phone_number_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    color_hex: Mapped[str] = mapped_column(String(7), default="#16A34A", nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    support_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)

    company = relationship("ClientCompany", lazy="joined")
    store = relationship("Store", lazy="joined")
    conversations = relationship("Conversation", back_populates="channel", lazy="selectin")
    messages = relationship("ConversationMessage", back_populates="channel", lazy="selectin")


class Tag(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("company_id", "name"),)

    company_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("client_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    store_id: Mapped[PGUUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    color_hex: Mapped[str] = mapped_column(String(7), default="#2563EB", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    company = relationship("ClientCompany", lazy="joined")
    store = relationship("Store", lazy="joined")
    contacts = relationship("Contact", secondary=contact_tags, back_populates="tags", lazy="selectin")
    conversations = relationship(
        "Conversation",
        secondary=conversation_tags,
        back_populates="tags",
        lazy="selectin",
    )


class Contact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "contacts"
    __table_args__ = (UniqueConstraint("company_id", "phone_number_e164"),)

    company_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("client_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    primary_store_id: Mapped[PGUUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String(180), nullable=False)
    phone_number_e164: Mapped[str] = mapped_column(String(32), nullable=False)
    alternate_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    document_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[ContactStatus] = mapped_column(
        Enum(ContactStatus, native_enum=False),
        default=ContactStatus.ACTIVE,
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    last_interaction_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    company = relationship("ClientCompany", lazy="joined")
    primary_store = relationship("Store", lazy="joined")
    tags = relationship("Tag", secondary=contact_tags, back_populates="contacts", lazy="selectin")
    conversations = relationship("Conversation", back_populates="contact", lazy="selectin")


class Conversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    company_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("client_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    store_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("whatsapp_channels.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    contact_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_user_id: Mapped[PGUUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("platform_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    subject: Mapped[str] = mapped_column(String(180), default="", nullable=False)
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus, native_enum=False),
        default=ConversationStatus.NEW,
        nullable=False,
        index=True,
    )
    priority: Mapped[ConversationPriority] = mapped_column(
        Enum(ConversationPriority, native_enum=False),
        default=ConversationPriority.NORMAL,
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(80), default="whatsapp", nullable=False)
    funnel_stage: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    first_customer_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_customer_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_human_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closure_reason: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    resolution_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)

    company = relationship("ClientCompany", lazy="joined")
    store = relationship("Store", lazy="joined")
    channel = relationship("WhatsAppChannel", back_populates="conversations", lazy="joined")
    contact = relationship("Contact", back_populates="conversations", lazy="joined")
    assigned_user = relationship("PlatformUser", lazy="joined")
    tags = relationship("Tag", secondary=conversation_tags, back_populates="conversations", lazy="selectin")
    messages = relationship(
        "ConversationMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    events = relationship(
        "ConversationEvent",
        back_populates="conversation",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    assignments = relationship(
        "ConversationAssignment",
        back_populates="conversation",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ConversationMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (UniqueConstraint("channel_id", "provider_message_id"),)

    company_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("client_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    store_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("whatsapp_channels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_user_id: Mapped[PGUUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("platform_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    direction: Mapped[MessageDirection] = mapped_column(
        Enum(MessageDirection, native_enum=False),
        nullable=False,
    )
    sender_type: Mapped[MessageSenderType] = mapped_column(
        Enum(MessageSenderType, native_enum=False),
        nullable=False,
    )
    message_type: Mapped[MessageType] = mapped_column(
        Enum(MessageType, native_enum=False),
        default=MessageType.TEXT,
        nullable=False,
    )
    delivery_status: Mapped[MessageDeliveryStatus] = mapped_column(
        Enum(MessageDeliveryStatus, native_enum=False),
        default=MessageDeliveryStatus.PENDING,
        nullable=False,
    )
    provider_message_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    text_body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_human: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    conversation = relationship("Conversation", back_populates="messages", lazy="joined")
    channel = relationship("WhatsAppChannel", back_populates="messages", lazy="joined")
    author_user = relationship("PlatformUser", lazy="joined")


class ConversationEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversation_events"

    company_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("client_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    store_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_user_id: Mapped[PGUUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("platform_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[ConversationEventType] = mapped_column(
        Enum(ConversationEventType, native_enum=False),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    conversation = relationship("Conversation", back_populates="events", lazy="joined")
    actor = relationship("PlatformUser", lazy="joined")


class ConversationAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversation_assignments"

    company_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("client_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    store_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_user_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("platform_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    assigned_by_user_id: Mapped[PGUUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("platform_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    conversation = relationship("Conversation", back_populates="assignments", lazy="joined")
    assigned_user = relationship("PlatformUser", foreign_keys=[assigned_user_id], lazy="joined")
    assigned_by_user = relationship("PlatformUser", foreign_keys=[assigned_by_user_id], lazy="joined")
