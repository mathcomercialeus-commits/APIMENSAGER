from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import BillingCustomer, BillingPlan, BillingPlanVersion, BillingProviderEvent, Invoice, Payment, PaymentEvent, Subscription
from app.models.enums import BillingProvider, InvoiceStatus, PaymentMethod, PaymentStatus, SubscriptionStatus
from app.models.tenant import ClientCompany, Store
from app.schemas.billing import (
    BillingCustomerRead,
    BillingPlanRead,
    BillingPlanVersionRead,
    CompanyBillingSummary,
    InvoiceRead,
    PaymentRead,
    SubscriptionRead,
)
from app.services.asaas import AsaasClient


def _money(value: Decimal | float | int | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def serialize_plan(plan: BillingPlan) -> BillingPlanRead:
    return BillingPlanRead(
        id=plan.id,
        code=plan.code,
        name=plan.name,
        description=plan.description,
        is_active=plan.is_active,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


def serialize_plan_version(version: BillingPlanVersion) -> BillingPlanVersionRead:
    return BillingPlanVersionRead(
        id=version.id,
        plan_id=version.plan_id,
        version_number=version.version_number,
        billing_scope=version.billing_scope.value,
        billing_cycle=version.billing_cycle.value,
        base_amount=_money(version.base_amount),
        store_amount=_money(version.store_amount),
        user_amount=_money(version.user_amount),
        channel_amount=_money(version.channel_amount),
        included_stores=version.included_stores,
        included_users=version.included_users,
        included_channels=version.included_channels,
        trial_days=version.trial_days,
        is_current=version.is_current,
        created_at=version.created_at,
        updated_at=version.updated_at,
    )


def serialize_customer(customer: BillingCustomer) -> BillingCustomerRead:
    return BillingCustomerRead(
        id=customer.id,
        company_id=customer.company_id,
        provider=customer.provider.value,
        provider_customer_id=customer.provider_customer_id,
        name_snapshot=customer.name_snapshot,
        email_snapshot=customer.email_snapshot,
        document_number_snapshot=customer.document_number_snapshot,
        created_at=customer.created_at,
        updated_at=customer.updated_at,
    )


def serialize_subscription(subscription: Subscription) -> SubscriptionRead:
    return SubscriptionRead(
        id=subscription.id,
        company_id=subscription.company_id,
        store_id=subscription.store_id,
        customer_id=subscription.customer_id,
        plan_version_id=subscription.plan_version_id,
        provider=subscription.provider.value,
        provider_subscription_id=subscription.provider_subscription_id,
        scope=subscription.scope.value,
        status=subscription.status.value,
        billing_cycle=subscription.billing_cycle.value,
        price_amount=_money(subscription.price_amount),
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        next_due_date=subscription.next_due_date,
        trial_ends_at=subscription.trial_ends_at,
        canceled_at=subscription.canceled_at,
        suspended_at=subscription.suspended_at,
        created_at=subscription.created_at,
        updated_at=subscription.updated_at,
    )


def serialize_invoice(invoice: Invoice) -> InvoiceRead:
    return InvoiceRead(
        id=invoice.id,
        company_id=invoice.company_id,
        store_id=invoice.store_id,
        subscription_id=invoice.subscription_id,
        provider=invoice.provider.value,
        provider_invoice_id=invoice.provider_invoice_id,
        status=invoice.status.value,
        amount=_money(invoice.amount),
        due_date=invoice.due_date,
        paid_at=invoice.paid_at,
        description=invoice.description,
        invoice_url=invoice.invoice_url,
        bank_slip_url=invoice.bank_slip_url,
        pix_qr_code_url=invoice.pix_qr_code_url,
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
    )


def serialize_payment(payment: Payment) -> PaymentRead:
    return PaymentRead(
        id=payment.id,
        invoice_id=payment.invoice_id,
        provider=payment.provider.value,
        provider_payment_id=payment.provider_payment_id,
        method=payment.method.value if payment.method else None,
        status=payment.status.value,
        amount=_money(payment.amount),
        paid_at=payment.paid_at,
        created_at=payment.created_at,
        updated_at=payment.updated_at,
    )


async def ensure_billing_customer(
    session: AsyncSession,
    *,
    company: ClientCompany,
) -> BillingCustomer:
    existing = await session.scalar(
        select(BillingCustomer).where(
            BillingCustomer.company_id == company.id,
            BillingCustomer.provider == BillingProvider.ASAAS,
        )
    )
    if existing:
        return existing

    client = AsaasClient()
    payload = await client.create_customer(
        name=company.display_name,
        email=company.billing_email,
        cpf_cnpj=company.document_number,
        external_reference=str(company.id),
    )
    customer = BillingCustomer(
        company_id=company.id,
        provider=BillingProvider.ASAAS,
        provider_customer_id=payload["id"],
        name_snapshot=company.display_name,
        email_snapshot=company.billing_email,
        document_number_snapshot=company.document_number,
        raw_payload=payload,
    )
    session.add(customer)
    await session.flush()
    return customer


def calculate_subscription_amount(plan_version: BillingPlanVersion, store: Store | None) -> float:
    amount = _money(plan_version.base_amount)
    if store and plan_version.billing_scope.value == "store":
        amount += _money(plan_version.store_amount)
    return amount


async def build_company_billing_summary(
    session: AsyncSession,
    *,
    company_id: UUID,
) -> CompanyBillingSummary:
    subscription = await session.scalar(
        select(Subscription)
        .where(Subscription.company_id == company_id)
        .order_by(Subscription.created_at.desc())
    )
    invoices = (
        await session.scalars(
            select(Invoice)
            .where(Invoice.company_id == company_id)
            .order_by(Invoice.due_date.desc().nullslast(), Invoice.created_at.desc())
            .limit(10)
        )
    ).all()
    payments = (
        await session.scalars(
            select(Payment)
            .join(Invoice, Invoice.id == Payment.invoice_id)
            .where(Invoice.company_id == company_id)
            .order_by(Payment.paid_at.desc().nullslast(), Payment.created_at.desc())
            .limit(10)
        )
    ).all()
    return CompanyBillingSummary(
        company_id=company_id,
        subscription=serialize_subscription(subscription) if subscription else None,
        open_invoices=[serialize_invoice(item) for item in invoices],
        recent_payments=[serialize_payment(item) for item in payments],
    )


def map_asaas_invoice_status(raw_status: str | None) -> InvoiceStatus:
    mapping = {
        "PENDING": InvoiceStatus.PENDING,
        "CONFIRMED": InvoiceStatus.CONFIRMED,
        "RECEIVED": InvoiceStatus.PAID,
        "RECEIVED_IN_CASH": InvoiceStatus.PAID,
        "OVERDUE": InvoiceStatus.OVERDUE,
        "REFUNDED": InvoiceStatus.REFUNDED,
        "RECEIVED_PARTIALLY": InvoiceStatus.PAID,
        "DELETED": InvoiceStatus.CANCELED,
    }
    return mapping.get(raw_status or "", InvoiceStatus.PENDING)


def map_asaas_payment_status(raw_status: str | None) -> PaymentStatus:
    mapping = {
        "PENDING": PaymentStatus.PENDING,
        "CONFIRMED": PaymentStatus.CONFIRMED,
        "RECEIVED": PaymentStatus.RECEIVED,
        "RECEIVED_IN_CASH": PaymentStatus.RECEIVED,
        "OVERDUE": PaymentStatus.OVERDUE,
        "REFUNDED": PaymentStatus.REFUNDED,
        "RECEIVED_PARTIALLY": PaymentStatus.RECEIVED,
    }
    return mapping.get(raw_status or "", PaymentStatus.PENDING)


def map_asaas_method(raw_billing_type: str | None) -> PaymentMethod | None:
    mapping = {
        "BOLETO": PaymentMethod.BOLETO,
        "PIX": PaymentMethod.PIX,
        "CREDIT_CARD": PaymentMethod.CREDIT_CARD,
    }
    return mapping.get(raw_billing_type or "")


def derive_asaas_event_identity(payload: dict) -> tuple[str, str | None, dict, str | None]:
    event_type = payload.get("event") or "UNKNOWN"
    payment_data = payload.get("payment") or {}
    subscription_provider_id = payment_data.get("subscription")

    provider_event_id = None
    if payment_data.get("id"):
        provider_event_id = f"{event_type}:{payment_data['id']}"
    elif subscription_provider_id:
        provider_event_id = f"{event_type}:{subscription_provider_id}"
    return event_type, provider_event_id, payment_data, subscription_provider_id


async def process_asaas_webhook(
    session: AsyncSession,
    payload: dict,
    *,
    provider_event: BillingProviderEvent | None = None,
) -> None:
    event_type, provider_event_id, payment_data, subscription_provider_id = derive_asaas_event_identity(payload)

    subscription = None
    if subscription_provider_id:
        subscription = await session.scalar(
            select(Subscription).where(
                Subscription.provider == BillingProvider.ASAAS,
                Subscription.provider_subscription_id == subscription_provider_id,
            )
        )

    if provider_event is None:
        existing_provider_event = await session.scalar(
            select(BillingProviderEvent).where(
                BillingProviderEvent.provider == BillingProvider.ASAAS,
                BillingProviderEvent.provider_event_id == provider_event_id,
            )
        )
        if existing_provider_event:
            return

    invoice = None
    payment = None
    if payment_data.get("id"):
        invoice = await session.scalar(
            select(Invoice).where(
                Invoice.provider == BillingProvider.ASAAS,
                Invoice.provider_invoice_id == payment_data["id"],
            )
        )
        if not invoice and subscription:
            invoice = Invoice(
                company_id=subscription.company_id,
                store_id=subscription.store_id,
                subscription_id=subscription.id,
                provider=BillingProvider.ASAAS,
                provider_invoice_id=payment_data["id"],
                amount=payment_data.get("value", 0),
                description=payment_data.get("description") or "",
            )
            session.add(invoice)
            await session.flush()

        if invoice:
            invoice.status = map_asaas_invoice_status(payment_data.get("status"))
            invoice.amount = payment_data.get("value", 0)
            invoice.description = payment_data.get("description") or invoice.description
            invoice.due_date = date.fromisoformat(payment_data["dueDate"]) if payment_data.get("dueDate") else None
            invoice.paid_at = (
                datetime.fromisoformat(payment_data["paymentDate"]).replace(tzinfo=timezone.utc)
                if payment_data.get("paymentDate")
                else None
            )
            invoice.invoice_url = payment_data.get("invoiceUrl")
            invoice.bank_slip_url = payment_data.get("bankSlipUrl")
            invoice.pix_qr_code_url = payment_data.get("pixQrCodeUrl")
            invoice.raw_payload = payment_data

            payment = await session.scalar(
                select(Payment).where(
                    Payment.provider == BillingProvider.ASAAS,
                    Payment.provider_payment_id == payment_data["id"],
                )
            )
            if not payment:
                payment = Payment(
                    invoice_id=invoice.id,
                    provider=BillingProvider.ASAAS,
                    provider_payment_id=payment_data["id"],
                    amount=payment_data.get("value", 0),
                )
                session.add(payment)
                await session.flush()

            payment.method = map_asaas_method(payment_data.get("billingType"))
            payment.status = map_asaas_payment_status(payment_data.get("status"))
            payment.amount = payment_data.get("value", 0)
            payment.paid_at = invoice.paid_at
            payment.raw_payload = payment_data

            existing_payment_event = None
            if provider_event_id:
                existing_payment_event = await session.scalar(
                    select(PaymentEvent).where(
                        PaymentEvent.payment_id == payment.id,
                        PaymentEvent.provider == BillingProvider.ASAAS,
                        PaymentEvent.provider_event_id == provider_event_id,
                    )
                )
            if not existing_payment_event:
                session.add(
                    PaymentEvent(
                        payment_id=payment.id,
                        provider=BillingProvider.ASAAS,
                        event_type=event_type,
                        provider_event_id=provider_event_id,
                        raw_payload=payload,
                    )
                )

    if subscription:
        if event_type in {"PAYMENT_RECEIVED", "PAYMENT_CONFIRMED"}:
            subscription.status = SubscriptionStatus.ACTIVE
        elif event_type == "PAYMENT_OVERDUE":
            subscription.status = SubscriptionStatus.PAST_DUE
        elif event_type in {"SUBSCRIPTION_DELETED", "SUBSCRIPTION_CANCELED"}:
            subscription.status = SubscriptionStatus.CANCELED
            subscription.canceled_at = datetime.now(timezone.utc)
        elif event_type in {"SUBSCRIPTION_RESTORED", "SUBSCRIPTION_UPDATED"}:
            subscription.status = SubscriptionStatus.ACTIVE
        if payment_data.get("dueDate"):
            subscription.next_due_date = date.fromisoformat(payment_data["dueDate"])

    if provider_event is None:
        provider_event = BillingProviderEvent(provider=BillingProvider.ASAAS)
        session.add(provider_event)

    provider_event.provider = BillingProvider.ASAAS
    provider_event.provider_event_id = provider_event_id
    provider_event.event_type = event_type
    provider_event.company_id = subscription.company_id if subscription else None
    provider_event.subscription_id = subscription.id if subscription else None
    provider_event.invoice_id = invoice.id if invoice else None
    provider_event.raw_payload = payload
    provider_event.processing_status = "processed"
    provider_event.processing_notes = "Webhook do billing processado com sucesso."
    provider_event.processed_at = datetime.now(timezone.utc)
