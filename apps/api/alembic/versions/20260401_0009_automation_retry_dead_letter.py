"""automation retry dead letter

Revision ID: 20260401_0009
Revises: 20260401_0008
Create Date: 2026-04-01 08:45:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260401_0009"
down_revision = "20260401_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "automation_executions",
        sa.Column("processing_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("automation_executions", sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("automation_executions", sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("automation_executions", sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("automation_executions", "processing_attempts", server_default=None)


def downgrade() -> None:
    op.drop_column("automation_executions", "dead_lettered_at")
    op.drop_column("automation_executions", "next_retry_at")
    op.drop_column("automation_executions", "last_attempt_at")
    op.drop_column("automation_executions", "processing_attempts")
