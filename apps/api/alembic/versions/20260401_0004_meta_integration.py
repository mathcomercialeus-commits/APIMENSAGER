"""meta integration

Revision ID: 20260401_0004
Revises: 20260401_0003
Create Date: 2026-04-01 03:20:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260401_0004"
down_revision = "20260401_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("last_customer_message_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "channel_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("app_id", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("business_account_id", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("graph_api_version", sa.String(length=16), nullable=False, server_default="v21.0"),
        sa.Column("webhook_callback_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("verify_token_hint", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("access_token_last4", sa.String(length=8), nullable=False, server_default=""),
        sa.Column("encrypted_access_token", sa.Text(), nullable=False, server_default=""),
        sa.Column("encrypted_app_secret", sa.Text(), nullable=False, server_default=""),
        sa.Column("encrypted_webhook_verify_token", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("last_healthcheck_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["channel_id"], ["whatsapp_channels.id"], name=op.f("fk_channel_credentials_channel_id_whatsapp_channels"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_channel_credentials")),
        sa.UniqueConstraint("channel_id", name=op.f("uq_channel_credentials_channel_id")),
    )

    op.create_table(
        "message_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("meta_template_id", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("language_code", sa.String(length=16), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="UNKNOWN"),
        sa.Column("components_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_message_templates")),
        sa.UniqueConstraint("name", "language_code", name="uq_message_templates_name_language"),
    )

    op.create_table(
        "channel_templates",
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["channel_id"], ["whatsapp_channels.id"], name=op.f("fk_channel_templates_channel_id_whatsapp_channels"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_id"], ["message_templates.id"], name=op.f("fk_channel_templates_template_id_message_templates"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("channel_id", "template_id", name=op.f("pk_channel_templates")),
    )

    op.create_table(
        "webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("phone_number_id", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("headers", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("signature_valid", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("processing_status", sa.String(length=40), nullable=False, server_default="received"),
        sa.Column("processing_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["channel_id"], ["whatsapp_channels.id"], name=op.f("fk_webhook_events_channel_id_whatsapp_channels"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_webhook_events")),
    )


def downgrade() -> None:
    op.drop_table("webhook_events")
    op.drop_table("channel_templates")
    op.drop_table("message_templates")
    op.drop_table("channel_credentials")
    op.drop_column("conversations", "last_customer_message_at")
