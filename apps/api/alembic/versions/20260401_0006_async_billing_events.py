"""async billing events

Revision ID: 20260401_0006
Revises: 20260401_0005
Create Date: 2026-04-01 05:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260401_0006"
down_revision = "20260401_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "billing_provider_events",
        sa.Column("headers", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "billing_provider_events",
        sa.Column("processing_status", sa.String(length=40), nullable=False, server_default="received"),
    )
    op.add_column(
        "billing_provider_events",
        sa.Column("processing_notes", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "billing_provider_events",
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column("billing_provider_events", "headers", server_default=None)
    op.alter_column("billing_provider_events", "processing_status", server_default=None)
    op.alter_column("billing_provider_events", "processing_notes", server_default=None)


def downgrade() -> None:
    op.drop_column("billing_provider_events", "processed_at")
    op.drop_column("billing_provider_events", "processing_notes")
    op.drop_column("billing_provider_events", "processing_status")
    op.drop_column("billing_provider_events", "headers")
