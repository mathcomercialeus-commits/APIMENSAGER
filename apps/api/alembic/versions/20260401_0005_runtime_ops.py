"""runtime ops

Revision ID: 20260401_0005
Revises: 20260401_0004
Create Date: 2026-04-01 04:10:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260401_0005"
down_revision = "20260401_0004"
branch_labels = None
depends_on = None


runtime_lifecycle_status = sa.Enum(
    "online",
    "degraded",
    "offline",
    "restarting",
    "suspended",
    name="runtimelifecyclestatus",
    native_enum=False,
)
restart_event_status = sa.Enum(
    "requested",
    "in_progress",
    "completed",
    "failed",
    "canceled",
    name="restarteventstatus",
    native_enum=False,
)
incident_severity = sa.Enum(
    "info",
    "warning",
    "error",
    "critical",
    name="incidentseverity",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "store_runtime_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("runtime_generation", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("lifecycle_status", runtime_lifecycle_status, nullable=False, server_default="offline"),
        sa.Column("heartbeat_interval_seconds", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("queue_depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active_jobs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("backlog_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_worker_shard", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("version", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("last_restart_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_restart_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_restart_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=False, server_default=""),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["client_companies.id"], name=op.f("fk_store_runtime_states_company_id_client_companies"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], name=op.f("fk_store_runtime_states_store_id_stores"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_store_runtime_states")),
        sa.UniqueConstraint("store_id", name="uq_store_runtime_states_store_id"),
    )
    op.create_index(op.f("ix_store_runtime_states_company_id"), "store_runtime_states", ["company_id"], unique=False)
    op.create_index(op.f("ix_store_runtime_states_store_id"), "store_runtime_states", ["store_id"], unique=False)
    op.create_index(op.f("ix_store_runtime_states_lifecycle_status"), "store_runtime_states", ["lifecycle_status"], unique=False)

    op.create_table(
        "store_health_checks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("runtime_state_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lifecycle_status", runtime_lifecycle_status, nullable=False),
        sa.Column("runtime_generation", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("queue_depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active_jobs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("backlog_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cpu_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("memory_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["client_companies.id"], name=op.f("fk_store_health_checks_company_id_client_companies"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["runtime_state_id"], ["store_runtime_states.id"], name=op.f("fk_store_health_checks_runtime_state_id_store_runtime_states"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], name=op.f("fk_store_health_checks_store_id_stores"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_store_health_checks")),
    )
    op.create_index(op.f("ix_store_health_checks_company_id"), "store_health_checks", ["company_id"], unique=False)
    op.create_index(op.f("ix_store_health_checks_store_id"), "store_health_checks", ["store_id"], unique=False)
    op.create_index(op.f("ix_store_health_checks_lifecycle_status"), "store_health_checks", ["lifecycle_status"], unique=False)

    op.create_table(
        "incident_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("severity", incident_severity, nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False, server_default="runtime"),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["client_companies.id"], name=op.f("fk_incident_events_company_id_client_companies"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["platform_users.id"], name=op.f("fk_incident_events_resolved_by_user_id_platform_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], name=op.f("fk_incident_events_store_id_stores"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incident_events")),
    )
    op.create_index(op.f("ix_incident_events_company_id"), "incident_events", ["company_id"], unique=False)
    op.create_index(op.f("ix_incident_events_store_id"), "incident_events", ["store_id"], unique=False)
    op.create_index(op.f("ix_incident_events_severity"), "incident_events", ["severity"], unique=False)

    op.create_table(
        "restart_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", restart_event_status, nullable=False, server_default="requested"),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=False, server_default=""),
        sa.Column("before_generation", sa.Integer(), nullable=False),
        sa.Column("after_generation", sa.Integer(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["client_companies.id"], name=op.f("fk_restart_events_company_id_client_companies"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["platform_users.id"], name=op.f("fk_restart_events_requested_by_user_id_platform_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], name=op.f("fk_restart_events_store_id_stores"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_restart_events")),
    )
    op.create_index(op.f("ix_restart_events_company_id"), "restart_events", ["company_id"], unique=False)
    op.create_index(op.f("ix_restart_events_store_id"), "restart_events", ["store_id"], unique=False)
    op.create_index(op.f("ix_restart_events_status"), "restart_events", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_restart_events_status"), table_name="restart_events")
    op.drop_index(op.f("ix_restart_events_store_id"), table_name="restart_events")
    op.drop_index(op.f("ix_restart_events_company_id"), table_name="restart_events")
    op.drop_table("restart_events")
    op.drop_index(op.f("ix_incident_events_severity"), table_name="incident_events")
    op.drop_index(op.f("ix_incident_events_store_id"), table_name="incident_events")
    op.drop_index(op.f("ix_incident_events_company_id"), table_name="incident_events")
    op.drop_table("incident_events")
    op.drop_index(op.f("ix_store_health_checks_lifecycle_status"), table_name="store_health_checks")
    op.drop_index(op.f("ix_store_health_checks_store_id"), table_name="store_health_checks")
    op.drop_index(op.f("ix_store_health_checks_company_id"), table_name="store_health_checks")
    op.drop_table("store_health_checks")
    op.drop_index(op.f("ix_store_runtime_states_lifecycle_status"), table_name="store_runtime_states")
    op.drop_index(op.f("ix_store_runtime_states_store_id"), table_name="store_runtime_states")
    op.drop_index(op.f("ix_store_runtime_states_company_id"), table_name="store_runtime_states")
    op.drop_table("store_runtime_states")
