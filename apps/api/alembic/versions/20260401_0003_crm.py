"""crm and conversations

Revision ID: 20260401_0003
Revises: 20260401_0002
Create Date: 2026-04-01 02:10:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260401_0003"
down_revision = "20260401_0002"
branch_labels = None
depends_on = None


channel_provider = sa.Enum("meta_cloud_api", name="channelprovider", native_enum=False)
channel_status = sa.Enum("active", "inactive", "error", name="channelstatus", native_enum=False)
contact_status = sa.Enum("active", "inactive", "blocked", name="contactstatus", native_enum=False)
conversation_status = sa.Enum(
    "new",
    "queued",
    "in_progress",
    "awaiting_customer",
    "awaiting_internal",
    "closed",
    "lost",
    "canceled",
    name="conversationstatus",
    native_enum=False,
)
conversation_priority = sa.Enum("low", "normal", "high", "urgent", name="conversationpriority", native_enum=False)
message_direction = sa.Enum("inbound", "outbound", name="messagedirection", native_enum=False)
message_sender_type = sa.Enum(
    "customer",
    "agent",
    "bot",
    "system",
    name="messagesendertype",
    native_enum=False,
)
message_type = sa.Enum(
    "text",
    "template",
    "image",
    "document",
    "audio",
    "video",
    "interactive",
    "system",
    name="messagetype",
    native_enum=False,
)
message_delivery_status = sa.Enum(
    "pending",
    "sent",
    "delivered",
    "read",
    "failed",
    name="messagedeliverystatus",
    native_enum=False,
)
conversation_event_type = sa.Enum(
    "opened",
    "status_changed",
    "assigned",
    "unassigned",
    "message_logged",
    "note_added",
    "tag_attached",
    "tag_removed",
    "updated",
    name="conversationeventtype",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "whatsapp_channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("provider", channel_provider, nullable=False, server_default="meta_cloud_api"),
        sa.Column("status", channel_status, nullable=False, server_default="active"),
        sa.Column("display_phone_number", sa.String(length=40), nullable=False),
        sa.Column("phone_number_e164", sa.String(length=32), nullable=False),
        sa.Column("external_phone_number_id", sa.String(length=120), nullable=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("color_hex", sa.String(length=7), nullable=False, server_default="#16A34A"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("support_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["client_companies.id"], name=op.f("fk_whatsapp_channels_company_id_client_companies"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], name=op.f("fk_whatsapp_channels_store_id_stores"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_whatsapp_channels")),
        sa.UniqueConstraint("company_id", "code", name=op.f("uq_whatsapp_channels_company_id")),
        sa.UniqueConstraint("company_id", "phone_number_e164", name="uq_whatsapp_channels_company_phone"),
        sa.UniqueConstraint("provider", "external_phone_number_id", name="uq_whatsapp_channels_provider_external"),
    )
    op.create_index(op.f("ix_whatsapp_channels_company_id"), "whatsapp_channels", ["company_id"], unique=False)
    op.create_index(op.f("ix_whatsapp_channels_store_id"), "whatsapp_channels", ["store_id"], unique=False)

    op.create_table(
        "tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("color_hex", sa.String(length=7), nullable=False, server_default="#2563EB"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["client_companies.id"], name=op.f("fk_tags_company_id_client_companies"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], name=op.f("fk_tags_store_id_stores"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tags")),
        sa.UniqueConstraint("company_id", "name", name="uq_tags_company_name"),
    )
    op.create_index(op.f("ix_tags_company_id"), "tags", ["company_id"], unique=False)
    op.create_index(op.f("ix_tags_store_id"), "tags", ["store_id"], unique=False)

    op.create_table(
        "contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("primary_store_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("full_name", sa.String(length=180), nullable=False),
        sa.Column("phone_number_e164", sa.String(length=32), nullable=False),
        sa.Column("alternate_phone", sa.String(length=32), nullable=True),
        sa.Column("email", sa.String(length=160), nullable=True),
        sa.Column("document_number", sa.String(length=32), nullable=True),
        sa.Column("status", contact_status, nullable=False, server_default="active"),
        sa.Column("source", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("last_interaction_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["client_companies.id"], name=op.f("fk_contacts_company_id_client_companies"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["primary_store_id"], ["stores.id"], name=op.f("fk_contacts_primary_store_id_stores"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contacts")),
        sa.UniqueConstraint("company_id", "phone_number_e164", name="uq_contacts_company_phone"),
    )
    op.create_index(op.f("ix_contacts_company_id"), "contacts", ["company_id"], unique=False)
    op.create_index(op.f("ix_contacts_primary_store_id"), "contacts", ["primary_store_id"], unique=False)

    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("subject", sa.String(length=180), nullable=False, server_default=""),
        sa.Column("status", conversation_status, nullable=False, server_default="new"),
        sa.Column("priority", conversation_priority, nullable=False, server_default="normal"),
        sa.Column("source", sa.String(length=80), nullable=False, server_default="whatsapp"),
        sa.Column("funnel_stage", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("first_customer_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_human_response_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closure_reason", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("resolution_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["platform_users.id"], name=op.f("fk_conversations_assigned_user_id_platform_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["channel_id"], ["whatsapp_channels.id"], name=op.f("fk_conversations_channel_id_whatsapp_channels"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["company_id"], ["client_companies.id"], name=op.f("fk_conversations_company_id_client_companies"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], name=op.f("fk_conversations_contact_id_contacts"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], name=op.f("fk_conversations_store_id_stores"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversations")),
    )
    op.create_index(op.f("ix_conversations_company_id"), "conversations", ["company_id"], unique=False)
    op.create_index(op.f("ix_conversations_store_id"), "conversations", ["store_id"], unique=False)
    op.create_index(op.f("ix_conversations_channel_id"), "conversations", ["channel_id"], unique=False)
    op.create_index(op.f("ix_conversations_contact_id"), "conversations", ["contact_id"], unique=False)
    op.create_index(op.f("ix_conversations_assigned_user_id"), "conversations", ["assigned_user_id"], unique=False)
    op.create_index(op.f("ix_conversations_status"), "conversations", ["status"], unique=False)

    op.create_table(
        "conversation_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("direction", message_direction, nullable=False),
        sa.Column("sender_type", message_sender_type, nullable=False),
        sa.Column("message_type", message_type, nullable=False, server_default="text"),
        sa.Column("delivery_status", message_delivery_status, nullable=False, server_default="pending"),
        sa.Column("provider_message_id", sa.String(length=120), nullable=True),
        sa.Column("text_body", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_human", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["author_user_id"], ["platform_users.id"], name=op.f("fk_conversation_messages_author_user_id_platform_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["channel_id"], ["whatsapp_channels.id"], name=op.f("fk_conversation_messages_channel_id_whatsapp_channels"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["client_companies.id"], name=op.f("fk_conversation_messages_company_id_client_companies"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], name=op.f("fk_conversation_messages_conversation_id_conversations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], name=op.f("fk_conversation_messages_store_id_stores"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversation_messages")),
        sa.UniqueConstraint("channel_id", "provider_message_id", name="uq_conversation_messages_channel_provider"),
    )
    op.create_index(op.f("ix_conversation_messages_company_id"), "conversation_messages", ["company_id"], unique=False)
    op.create_index(op.f("ix_conversation_messages_store_id"), "conversation_messages", ["store_id"], unique=False)
    op.create_index(op.f("ix_conversation_messages_channel_id"), "conversation_messages", ["channel_id"], unique=False)
    op.create_index(op.f("ix_conversation_messages_conversation_id"), "conversation_messages", ["conversation_id"], unique=False)

    op.create_table(
        "conversation_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", conversation_event_type, nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["platform_users.id"], name=op.f("fk_conversation_events_actor_user_id_platform_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["client_companies.id"], name=op.f("fk_conversation_events_company_id_client_companies"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], name=op.f("fk_conversation_events_conversation_id_conversations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], name=op.f("fk_conversation_events_store_id_stores"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversation_events")),
    )
    op.create_index(op.f("ix_conversation_events_company_id"), "conversation_events", ["company_id"], unique=False)
    op.create_index(op.f("ix_conversation_events_store_id"), "conversation_events", ["store_id"], unique=False)
    op.create_index(op.f("ix_conversation_events_conversation_id"), "conversation_events", ["conversation_id"], unique=False)
    op.create_index(op.f("ix_conversation_events_event_type"), "conversation_events", ["event_type"], unique=False)

    op.create_table(
        "conversation_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["assigned_by_user_id"], ["platform_users.id"], name=op.f("fk_conversation_assignments_assigned_by_user_id_platform_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["platform_users.id"], name=op.f("fk_conversation_assignments_assigned_user_id_platform_users"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["client_companies.id"], name=op.f("fk_conversation_assignments_company_id_client_companies"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], name=op.f("fk_conversation_assignments_conversation_id_conversations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], name=op.f("fk_conversation_assignments_store_id_stores"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversation_assignments")),
    )
    op.create_index(op.f("ix_conversation_assignments_company_id"), "conversation_assignments", ["company_id"], unique=False)
    op.create_index(op.f("ix_conversation_assignments_store_id"), "conversation_assignments", ["store_id"], unique=False)
    op.create_index(op.f("ix_conversation_assignments_conversation_id"), "conversation_assignments", ["conversation_id"], unique=False)

    op.create_table(
        "contact_tags",
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], name=op.f("fk_contact_tags_contact_id_contacts"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], name=op.f("fk_contact_tags_tag_id_tags"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("contact_id", "tag_id", name=op.f("pk_contact_tags")),
    )

    op.create_table(
        "conversation_tags",
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], name=op.f("fk_conversation_tags_conversation_id_conversations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], name=op.f("fk_conversation_tags_tag_id_tags"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("conversation_id", "tag_id", name=op.f("pk_conversation_tags")),
    )


def downgrade() -> None:
    op.drop_table("conversation_tags")
    op.drop_table("contact_tags")
    op.drop_index(op.f("ix_conversation_assignments_conversation_id"), table_name="conversation_assignments")
    op.drop_index(op.f("ix_conversation_assignments_store_id"), table_name="conversation_assignments")
    op.drop_index(op.f("ix_conversation_assignments_company_id"), table_name="conversation_assignments")
    op.drop_table("conversation_assignments")
    op.drop_index(op.f("ix_conversation_events_event_type"), table_name="conversation_events")
    op.drop_index(op.f("ix_conversation_events_conversation_id"), table_name="conversation_events")
    op.drop_index(op.f("ix_conversation_events_store_id"), table_name="conversation_events")
    op.drop_index(op.f("ix_conversation_events_company_id"), table_name="conversation_events")
    op.drop_table("conversation_events")
    op.drop_index(op.f("ix_conversation_messages_conversation_id"), table_name="conversation_messages")
    op.drop_index(op.f("ix_conversation_messages_channel_id"), table_name="conversation_messages")
    op.drop_index(op.f("ix_conversation_messages_store_id"), table_name="conversation_messages")
    op.drop_index(op.f("ix_conversation_messages_company_id"), table_name="conversation_messages")
    op.drop_table("conversation_messages")
    op.drop_index(op.f("ix_conversations_status"), table_name="conversations")
    op.drop_index(op.f("ix_conversations_assigned_user_id"), table_name="conversations")
    op.drop_index(op.f("ix_conversations_contact_id"), table_name="conversations")
    op.drop_index(op.f("ix_conversations_channel_id"), table_name="conversations")
    op.drop_index(op.f("ix_conversations_store_id"), table_name="conversations")
    op.drop_index(op.f("ix_conversations_company_id"), table_name="conversations")
    op.drop_table("conversations")
    op.drop_index(op.f("ix_contacts_primary_store_id"), table_name="contacts")
    op.drop_index(op.f("ix_contacts_company_id"), table_name="contacts")
    op.drop_table("contacts")
    op.drop_index(op.f("ix_tags_store_id"), table_name="tags")
    op.drop_index(op.f("ix_tags_company_id"), table_name="tags")
    op.drop_table("tags")
    op.drop_index(op.f("ix_whatsapp_channels_store_id"), table_name="whatsapp_channels")
    op.drop_index(op.f("ix_whatsapp_channels_company_id"), table_name="whatsapp_channels")
    op.drop_table("whatsapp_channels")
