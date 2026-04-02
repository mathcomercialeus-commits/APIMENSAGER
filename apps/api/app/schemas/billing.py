from datetime import date, datetime
from uuid import UUID

from app.schemas.common import APIModel


class BillingPlanCreate(APIModel):
    code: str
    name: str
    description: str = ""


class BillingPlanVersionCreate(APIModel):
    billing_scope: str
    billing_cycle: str
    base_amount: float
    store_amount: float = 0
    user_amount: float = 0
    channel_amount: float = 0
    included_stores: int = 1
    included_users: int = 1
    included_channels: int = 1
    trial_days: int = 0
    is_current: bool = False


class BillingPlanRead(APIModel):
    id: UUID
    code: str
    name: str
    description: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BillingPlanVersionRead(APIModel):
    id: UUID
    plan_id: UUID
    version_number: int
    billing_scope: str
    billing_cycle: str
    base_amount: float
    store_amount: float
    user_amount: float
    channel_amount: float
    included_stores: int
    included_users: int
    included_channels: int
    trial_days: int
    is_current: bool
    created_at: datetime
    updated_at: datetime


class BillingCustomerRead(APIModel):
    id: UUID
    company_id: UUID
    provider: str
    provider_customer_id: str
    name_snapshot: str
    email_snapshot: str | None
    document_number_snapshot: str | None
    created_at: datetime
    updated_at: datetime


class SubscriptionCreate(APIModel):
    company_id: UUID
    store_id: UUID | None = None
    plan_version_id: UUID
    payment_method: str
    description: str = ""


class SubscriptionRead(APIModel):
    id: UUID
    company_id: UUID
    store_id: UUID | None
    customer_id: UUID
    plan_version_id: UUID
    provider: str
    provider_subscription_id: str | None
    scope: str
    status: str
    billing_cycle: str
    price_amount: float
    current_period_start: date | None
    current_period_end: date | None
    next_due_date: date | None
    trial_ends_at: datetime | None
    canceled_at: datetime | None
    suspended_at: datetime | None
    created_at: datetime
    updated_at: datetime


class InvoiceRead(APIModel):
    id: UUID
    company_id: UUID
    store_id: UUID | None
    subscription_id: UUID | None
    provider: str
    provider_invoice_id: str | None
    status: str
    amount: float
    due_date: date | None
    paid_at: datetime | None
    description: str
    invoice_url: str | None
    bank_slip_url: str | None
    pix_qr_code_url: str | None
    created_at: datetime
    updated_at: datetime


class PaymentRead(APIModel):
    id: UUID
    invoice_id: UUID
    provider: str
    provider_payment_id: str | None
    method: str | None
    status: str
    amount: float
    paid_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CompanyBillingSummary(APIModel):
    company_id: UUID
    subscription: SubscriptionRead | None
    open_invoices: list[InvoiceRead]
    recent_payments: list[PaymentRead]


class BillingWebhookAck(APIModel):
    message: str
    event_id: UUID | None = None
    processing_status: str | None = None
