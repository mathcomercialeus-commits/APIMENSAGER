from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    BillingCycle,
    BillingProvider,
    BillingScope,
    InvoiceStatus,
    PaymentMethod,
    PaymentStatus,
    SubscriptionStatus,
)


class BillingPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "billing_plans"

    code: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    versions = relationship(
        "BillingPlanVersion",
        back_populates="plan",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class BillingPlanVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "billing_plan_versions"

    plan_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("billing_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    billing_scope: Mapped[BillingScope] = mapped_column(
        Enum(BillingScope, native_enum=False),
        nullable=False,
    )
    billing_cycle: Mapped[BillingCycle] = mapped_column(
        Enum(BillingCycle, native_enum=False),
        nullable=False,
    )
    base_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    store_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    user_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    channel_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    included_stores: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    included_users: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    included_channels: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    trial_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    plan = relationship("BillingPlan", back_populates="versions", lazy="joined")


class BillingCustomer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "billing_customers"
    __table_args__ = (UniqueConstraint("provider", "provider_customer_id"),)

    company_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("client_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[BillingProvider] = mapped_column(
        Enum(BillingProvider, native_enum=False),
        nullable=False,
        default=BillingProvider.ASAAS,
    )
    provider_customer_id: Mapped[str] = mapped_column(String(120), nullable=False)
    name_snapshot: Mapped[str] = mapped_column(String(180), nullable=False)
    email_snapshot: Mapped[str | None] = mapped_column(String(160), nullable=True)
    document_number_snapshot: Mapped[str | None] = mapped_column(String(32), nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    company = relationship("ClientCompany", lazy="joined")


class Subscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("provider", "provider_subscription_id"),)

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
    customer_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("billing_customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    plan_version_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("billing_plan_versions.id"),
        nullable=False,
    )
    provider: Mapped[BillingProvider] = mapped_column(
        Enum(BillingProvider, native_enum=False),
        nullable=False,
        default=BillingProvider.ASAAS,
    )
    provider_subscription_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    scope: Mapped[BillingScope] = mapped_column(
        Enum(BillingScope, native_enum=False),
        nullable=False,
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, native_enum=False),
        default=SubscriptionStatus.DRAFT,
        nullable=False,
    )
    billing_cycle: Mapped[BillingCycle] = mapped_column(
        Enum(BillingCycle, native_enum=False),
        nullable=False,
    )
    price_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    current_period_start: Mapped[date | None] = mapped_column(Date(), nullable=True)
    current_period_end: Mapped[date | None] = mapped_column(Date(), nullable=True)
    next_due_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    customer = relationship("BillingCustomer", lazy="joined")
    plan_version = relationship("BillingPlanVersion", lazy="joined")
    company = relationship("ClientCompany", lazy="joined")
    store = relationship("Store", lazy="joined")
    invoices = relationship("Invoice", back_populates="subscription", lazy="selectin")


class Invoice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("provider", "provider_invoice_id"),)

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
    subscription_id: Mapped[PGUUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provider: Mapped[BillingProvider] = mapped_column(
        Enum(BillingProvider, native_enum=False),
        nullable=False,
        default=BillingProvider.ASAAS,
    )
    provider_invoice_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, native_enum=False),
        default=InvoiceStatus.PENDING,
        nullable=False,
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    invoice_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    bank_slip_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    pix_qr_code_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    subscription = relationship("Subscription", back_populates="invoices", lazy="joined")
    payments = relationship("Payment", back_populates="invoice", lazy="selectin")


class Payment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("provider", "provider_payment_id"),)

    invoice_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[BillingProvider] = mapped_column(
        Enum(BillingProvider, native_enum=False),
        nullable=False,
        default=BillingProvider.ASAAS,
    )
    provider_payment_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    method: Mapped[PaymentMethod | None] = mapped_column(
        Enum(PaymentMethod, native_enum=False),
        nullable=True,
    )
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, native_enum=False),
        default=PaymentStatus.PENDING,
        nullable=False,
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    invoice = relationship("Invoice", back_populates="payments", lazy="joined")
    events = relationship("PaymentEvent", back_populates="payment", lazy="selectin")


class PaymentEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payment_events"

    payment_id: Mapped[PGUUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider: Mapped[BillingProvider] = mapped_column(
        Enum(BillingProvider, native_enum=False),
        nullable=False,
        default=BillingProvider.ASAAS,
    )
    event_type: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    provider_event_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    payment = relationship("Payment", back_populates="events", lazy="joined")


class BillingProviderEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "billing_provider_events"
    __table_args__ = (UniqueConstraint("provider", "provider_event_id"),)

    provider: Mapped[BillingProvider] = mapped_column(
        Enum(BillingProvider, native_enum=False),
        nullable=False,
        default=BillingProvider.ASAAS,
    )
    provider_event_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    event_type: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    company_id: Mapped[PGUUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("client_companies.id", ondelete="SET NULL"),
        nullable=True,
    )
    subscription_id: Mapped[PGUUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        nullable=True,
    )
    invoice_id: Mapped[PGUUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
    )
    headers: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    processing_status: Mapped[str] = mapped_column(String(40), default="received", nullable=False)
    processing_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    processing_attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dead_lettered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
