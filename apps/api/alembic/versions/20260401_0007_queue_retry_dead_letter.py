"""queue retry dead letter

Revision ID: 20260401_0007
Revises: 20260401_0006
Create Date: 2026-04-01 05:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260401_0007"
down_revision = "20260401_0006"
branch_labels = None
depends_on = None


def _add_queue_columns(table_name: str) -> None:
    op.add_column(table_name, sa.Column("processing_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column(table_name, sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(table_name, sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(table_name, sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column(table_name, "processing_attempts", server_default=None)


def _drop_queue_columns(table_name: str) -> None:
    op.drop_column(table_name, "dead_lettered_at")
    op.drop_column(table_name, "next_retry_at")
    op.drop_column(table_name, "last_attempt_at")
    op.drop_column(table_name, "processing_attempts")


def upgrade() -> None:
    _add_queue_columns("webhook_events")
    _add_queue_columns("billing_provider_events")


def downgrade() -> None:
    _drop_queue_columns("billing_provider_events")
    _drop_queue_columns("webhook_events")
