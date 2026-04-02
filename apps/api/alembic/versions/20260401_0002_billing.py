"""billing core

Revision ID: 20260401_0002
Revises: 20260401_0001
Create Date: 2026-04-01 00:30:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260401_0002"
down_revision = "20260401_0001"
branch_labels = None
depends_on = None


billing_provider = sa.Enum("asaas", name="billingprovider", native_enum=False)
billing_scope = sa.Enum("company", "store", name="billingscope", native_enum=False)
billing_cycle = sa.Enum(
    "weekly",
    "biweekly",
    "monthly",
    "quarterly",
    "semiannually",
    "yearly",
    name="billingcycle",
    native_enum=False,
)
subscription_status = sa.Enum(
    "draft",
    "trialing",
    "active",
    "past_due",
    "suspended",
    "canceled",
    name="subscriptionstatus",
    native_enum=False,
)
invoice_status = sa.Enum(
    "pending",
    "confirmed",
    "paid",
    "overdue",
    "canceled",
    "refunded",
    "failed",
    name="invoicestatus",
    native_enum=False,
)
payment_status = sa.Enum(
    "pending",
    "confirmed",
    "received",
    "overdue",
    "refunded",
    "failed",
    name="paymentstatus",
    native_enum=False,
)
payment_method = sa.Enum(
    "boleto",
    "pix",
    "credit_card",
    name="paymentmethod",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "billing_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_billing_plans")),
    )
    op.create_index(op.f("ix_billing_plans_code"), "billing_plans", ["code"], unique=True)

    op.create_table(
        "billing_plan_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("billing_scope", billing_scope, nullable=False),
        sa.Column("billing_cycle", billing_cycle, nullable=False),
        sa.Column("base_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("store_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("user_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("channel_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("included_stores", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("included_users", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("included_channels", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("trial_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["billing_plans.id"], name=op.f("fk_billing_plan_versions_plan_id_billing_plans"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_billing_plan_versions")),
    )

    op.create_table(
        "billing_customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", billing_provider, nullable=False, server_default="asaas"),
        sa.Column("provider_customer_id", sa.String(length=120), nullable=False),
        sa.Column("name_snapshot", sa.String(length=180), nullable=False),
        sa.Column("email_snapshot", sa.String(length=160), nullable=True),
        sa.Column("document_number_snapshot", sa.String(length=32), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["client_companies.id"], name=op.f("fk_billing_customers_company_id_client_companies"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_billing_customers")),
        sa.UniqueConstraint("provider", "provider_customer_id", name=op.f("uq_billing_customers_provider")),
    )
    op.create_index(op.f("ix_billing_customers_company_id"), "billing_customers", ["company_id"], unique=False)

    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", billing_provider, nullable=False, server_default="asaas"),
        sa.Column("provider_subscription_id", sa.String(length=120), nullable=True),
        sa.Column("scope", billing_scope, nullable=False),
        sa.Column("status", subscription_status, nullable=False, server_default="draft"),
        sa.Column("billing_cycle", billing_cycle, nullable=False),
        sa.Column("price_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("current_period_start", sa.Date(), nullable=True),
        sa.Column("current_period_end", sa.Date(), nullable=True),
        sa.Column("next_due_date", sa.Date(), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["client_companies.id"], name=op.f("fk_subscriptions_company_id_client_companies"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["billing_customers.id"], name=op.f("fk_subscriptions_customer_id_billing_customers"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_version_id"], ["billing_plan_versions.id"], name=op.f("fk_subscriptions_plan_version_id_billing_plan_versions")),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], name=op.f("fk_subscriptions_store_id_stores"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subscriptions")),
        sa.UniqueConstraint("provider", "provider_subscription_id", name=op.f("uq_subscriptions_provider")),
    )
    op.create_index(op.f("ix_subscriptions_company_id"), "subscriptions", ["company_id"], unique=False)
    op.create_index(op.f("ix_subscriptions_store_id"), "subscriptions", ["store_id"], unique=False)

    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", billing_provider, nullable=False, server_default="asaas"),
        sa.Column("provider_invoice_id", sa.String(length=120), nullable=True),
        sa.Column("status", invoice_status, nullable=False, server_default="pending"),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("invoice_url", sa.Text(), nullable=True),
        sa.Column("bank_slip_url", sa.Text(), nullable=True),
        sa.Column("pix_qr_code_url", sa.Text(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["client_companies.id"], name=op.f("fk_invoices_company_id_client_companies"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], name=op.f("fk_invoices_store_id_stores"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.id"], name=op.f("fk_invoices_subscription_id_subscriptions"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invoices")),
        sa.UniqueConstraint("provider", "provider_invoice_id", name=op.f("uq_invoices_provider")),
    )
    op.create_index(op.f("ix_invoices_company_id"), "invoices", ["company_id"], unique=False)
    op.create_index(op.f("ix_invoices_store_id"), "invoices", ["store_id"], unique=False)
    op.create_index(op.f("ix_invoices_subscription_id"), "invoices", ["subscription_id"], unique=False)

    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", billing_provider, nullable=False, server_default="asaas"),
        sa.Column("provider_payment_id", sa.String(length=120), nullable=True),
        sa.Column("method", payment_method, nullable=True),
        sa.Column("status", payment_status, nullable=False, server_default="pending"),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], name=op.f("fk_payments_invoice_id_invoices"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payments")),
        sa.UniqueConstraint("provider", "provider_payment_id", name=op.f("uq_payments_provider")),
    )

    op.create_table(
        "payment_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", billing_provider, nullable=False, server_default="asaas"),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("provider_event_id", sa.String(length=120), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], name=op.f("fk_payment_events_payment_id_payments"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_events")),
    )
    op.create_index(op.f("ix_payment_events_event_type"), "payment_events", ["event_type"], unique=False)

    op.create_table(
        "billing_provider_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", billing_provider, nullable=False, server_default="asaas"),
        sa.Column("provider_event_id", sa.String(length=120), nullable=True),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["client_companies.id"], name=op.f("fk_billing_provider_events_company_id_client_companies"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], name=op.f("fk_billing_provider_events_invoice_id_invoices"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.id"], name=op.f("fk_billing_provider_events_subscription_id_subscriptions"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_billing_provider_events")),
        sa.UniqueConstraint("provider", "provider_event_id", name=op.f("uq_billing_provider_events_provider")),
    )
    op.create_index(op.f("ix_billing_provider_events_event_type"), "billing_provider_events", ["event_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_billing_provider_events_event_type"), table_name="billing_provider_events")
    op.drop_table("billing_provider_events")
    op.drop_index(op.f("ix_payment_events_event_type"), table_name="payment_events")
    op.drop_table("payment_events")
    op.drop_table("payments")
    op.drop_index(op.f("ix_invoices_subscription_id"), table_name="invoices")
    op.drop_index(op.f("ix_invoices_store_id"), table_name="invoices")
    op.drop_index(op.f("ix_invoices_company_id"), table_name="invoices")
    op.drop_table("invoices")
    op.drop_index(op.f("ix_subscriptions_store_id"), table_name="subscriptions")
    op.drop_index(op.f("ix_subscriptions_company_id"), table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_index(op.f("ix_billing_customers_company_id"), table_name="billing_customers")
    op.drop_table("billing_customers")
    op.drop_table("billing_plan_versions")
    op.drop_index(op.f("ix_billing_plans_code"), table_name="billing_plans")
    op.drop_table("billing_plans")
