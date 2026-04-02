"""automations

Revision ID: 20260401_0008
Revises: 20260401_0007
Create Date: 2026-04-01 06:15:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260401_0008"
down_revision = "20260401_0007"
branch_labels = None
depends_on = None


automation_trigger_type = sa.Enum("manual", "conversation_opened", "conversation_assigned", "out_of_hours", name="automationtriggertype", native_enum=False)
automation_action_type = sa.Enum("send_text", "send_template", "close_conversation", name="automationactiontype", native_enum=False)
automation_execution_status = sa.Enum("queued", "processing", "executed", "skipped", "failed", name="automationexecutionstatus", native_enum=False)


def upgrade() -> None:
    op.create_table(
        "automation_rules",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("trigger_type", automation_trigger_type, nullable=False),
        sa.Column("action_type", automation_action_type, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("respect_customer_window", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("message_body", sa.Text(), nullable=False, server_default=""),
        sa.Column("template_name", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("template_language_code", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("settings_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("last_executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["company_id"], ["client_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["channel_id"], ["whatsapp_channels.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("store_id", "name"),
    )
    op.create_index(op.f("ix_automation_rules_company_id"), "automation_rules", ["company_id"], unique=False)
    op.create_index(op.f("ix_automation_rules_store_id"), "automation_rules", ["store_id"], unique=False)
    op.create_index(op.f("ix_automation_rules_channel_id"), "automation_rules", ["channel_id"], unique=False)
    op.alter_column("automation_rules", "description", server_default=None)
    op.alter_column("automation_rules", "is_active", server_default=None)
    op.alter_column("automation_rules", "priority", server_default=None)
    op.alter_column("automation_rules", "respect_customer_window", server_default=None)
    op.alter_column("automation_rules", "message_body", server_default=None)
    op.alter_column("automation_rules", "template_name", server_default=None)
    op.alter_column("automation_rules", "template_language_code", server_default=None)
    op.alter_column("automation_rules", "settings_json", server_default=None)

    op.create_table(
        "automation_executions",
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", automation_execution_status, nullable=False, server_default="queued"),
        sa.Column("rendered_message", sa.Text(), nullable=False, server_default=""),
        sa.Column("result_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("provider_message_id", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("provider_response", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["rule_id"], ["automation_rules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["client_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["channel_id"], ["whatsapp_channels.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["platform_users.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_automation_executions_rule_id"), "automation_executions", ["rule_id"], unique=False)
    op.create_index(op.f("ix_automation_executions_company_id"), "automation_executions", ["company_id"], unique=False)
    op.create_index(op.f("ix_automation_executions_store_id"), "automation_executions", ["store_id"], unique=False)
    op.create_index(op.f("ix_automation_executions_channel_id"), "automation_executions", ["channel_id"], unique=False)
    op.create_index(op.f("ix_automation_executions_conversation_id"), "automation_executions", ["conversation_id"], unique=False)
    op.create_index(op.f("ix_automation_executions_status"), "automation_executions", ["status"], unique=False)
    op.alter_column("automation_executions", "status", server_default=None)
    op.alter_column("automation_executions", "rendered_message", server_default=None)
    op.alter_column("automation_executions", "result_notes", server_default=None)
    op.alter_column("automation_executions", "provider_message_id", server_default=None)
    op.alter_column("automation_executions", "provider_response", server_default=None)
    op.alter_column("automation_executions", "metadata_json", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_automation_executions_status"), table_name="automation_executions")
    op.drop_index(op.f("ix_automation_executions_conversation_id"), table_name="automation_executions")
    op.drop_index(op.f("ix_automation_executions_channel_id"), table_name="automation_executions")
    op.drop_index(op.f("ix_automation_executions_store_id"), table_name="automation_executions")
    op.drop_index(op.f("ix_automation_executions_company_id"), table_name="automation_executions")
    op.drop_index(op.f("ix_automation_executions_rule_id"), table_name="automation_executions")
    op.drop_table("automation_executions")
    op.drop_index(op.f("ix_automation_rules_channel_id"), table_name="automation_rules")
    op.drop_index(op.f("ix_automation_rules_store_id"), table_name="automation_rules")
    op.drop_index(op.f("ix_automation_rules_company_id"), table_name="automation_rules")
    op.drop_table("automation_rules")
