from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor, require_superadmin, request_ip
from app.core.config import settings
from app.core.database import get_db_session
from app.models.billing import BillingCustomer, BillingPlan, BillingPlanVersion, Invoice, Payment, Subscription
from app.models.billing import BillingProviderEvent
from app.models.enums import BillingProvider, PaymentMethod, SubscriptionStatus
from app.schemas.billing import (
    BillingCustomerRead,
    BillingPlanCreate,
    BillingPlanRead,
    BillingPlanVersionCreate,
    BillingPlanVersionRead,
    BillingWebhookAck,
    CompanyBillingSummary,
    InvoiceRead,
    PaymentRead,
    SubscriptionCreate,
    SubscriptionRead,
)
from app.services.access import CurrentActor, get_company_or_404, get_store_or_404
from app.services.asaas import BillingIntegrationError, AsaasClient
from app.services.audit import record_audit_log
from app.services.billing import (
    build_company_billing_summary,
    calculate_subscription_amount,
    derive_asaas_event_identity,
    ensure_billing_customer,
    process_asaas_webhook,
    serialize_customer,
    serialize_invoice,
    serialize_payment,
    serialize_plan,
    serialize_plan_version,
    serialize_subscription,
)
from app.workers.tasks import enqueue_billing_provider_event


router = APIRouter()


@router.get("/plans", response_model=list[BillingPlanRead])
async def list_plans(
    session: AsyncSession = Depends(get_db_session),
    _: CurrentActor = Depends(get_current_actor),
) -> list[BillingPlanRead]:
    plans = (await session.scalars(select(BillingPlan).order_by(BillingPlan.name))).all()
    return [serialize_plan(plan) for plan in plans]


@router.post("/plans", response_model=BillingPlanRead, status_code=status.HTTP_201_CREATED)
async def create_plan(
    payload: BillingPlanCreate,
    request: Request,
    actor: CurrentActor = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db_session),
) -> BillingPlanRead:
    plan = BillingPlan(**payload.model_dump())
    session.add(plan)
    await session.flush()
    await record_audit_log(
        session,
        action="billing.plan_created",
        resource_type="billing_plan",
        actor_user_id=actor.user.id,
        resource_id=str(plan.id),
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
    )
    await session.commit()
    return serialize_plan(plan)


@router.post("/plans/{plan_id}/versions", response_model=BillingPlanVersionRead, status_code=status.HTTP_201_CREATED)
async def create_plan_version(
    plan_id: UUID,
    payload: BillingPlanVersionCreate,
    request: Request,
    actor: CurrentActor = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db_session),
) -> BillingPlanVersionRead:
    plan = await session.get(BillingPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plano nao encontrado.")

    latest_number = (
        await session.scalar(
            select(BillingPlanVersion.version_number)
            .where(BillingPlanVersion.plan_id == plan.id)
            .order_by(BillingPlanVersion.version_number.desc())
            .limit(1)
        )
    ) or 0

    if payload.is_current:
        current_versions = (
            await session.scalars(select(BillingPlanVersion).where(BillingPlanVersion.plan_id == plan.id))
        ).all()
        for version in current_versions:
            version.is_current = False

    version = BillingPlanVersion(
        plan_id=plan.id,
        version_number=latest_number + 1,
        **payload.model_dump(),
    )
    session.add(version)
    await session.flush()
    await record_audit_log(
        session,
        action="billing.plan_version_created",
        resource_type="billing_plan_version",
        actor_user_id=actor.user.id,
        resource_id=str(version.id),
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"plan_id": str(plan.id), "version_number": version.version_number},
    )
    await session.commit()
    return serialize_plan_version(version)


@router.get("/plans/{plan_id}/versions", response_model=list[BillingPlanVersionRead])
async def list_plan_versions(
    plan_id: UUID,
    _: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> list[BillingPlanVersionRead]:
    plan = await session.get(BillingPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plano nao encontrado.")

    versions = (
        await session.scalars(
            select(BillingPlanVersion)
            .where(BillingPlanVersion.plan_id == plan.id)
            .order_by(BillingPlanVersion.version_number.desc())
        )
    ).all()
    return [serialize_plan_version(item) for item in versions]


@router.post("/companies/{company_id}/customers/sync", response_model=BillingCustomerRead)
async def sync_billing_customer(
    company_id: UUID,
    request: Request,
    actor: CurrentActor = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db_session),
) -> BillingCustomerRead:
    company = await get_company_or_404(session, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa nao encontrada.")
    try:
        customer = await ensure_billing_customer(session, company=company)
    except BillingIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    await record_audit_log(
        session,
        action="billing.customer_synced",
        resource_type="billing_customer",
        actor_user_id=actor.user.id,
        resource_id=str(customer.id),
        company_id=company.id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
    )
    await session.commit()
    return serialize_customer(customer)


@router.post("/subscriptions", response_model=SubscriptionRead, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    payload: SubscriptionCreate,
    request: Request,
    actor: CurrentActor = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db_session),
) -> SubscriptionRead:
    company = await get_company_or_404(session, payload.company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa nao encontrada.")

    store = None
    if payload.store_id:
        store = await get_store_or_404(session, payload.store_id)
        if not store or store.company_id != company.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Loja invalida para esta empresa.")

    plan_version = await session.get(BillingPlanVersion, payload.plan_version_id)
    if not plan_version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Versao de plano nao encontrada.")

    try:
        payment_method = PaymentMethod(payload.payment_method)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Metodo de pagamento invalido.") from exc

    try:
        customer = await ensure_billing_customer(session, company=company)
        amount = calculate_subscription_amount(plan_version, store)
        next_due_date = date.today() + timedelta(days=plan_version.trial_days or 0)
        provider_payload = await AsaasClient().create_subscription(
            customer_id=customer.provider_customer_id,
            cycle=plan_version.billing_cycle,
            payment_method=payment_method,
            value=amount,
            next_due_date=next_due_date,
            description=payload.description or f"Plano {plan_version.plan.name}",
            external_reference=f"{company.id}:{store.id if store else 'company'}:{plan_version.id}",
        )
    except BillingIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    subscription = Subscription(
        company_id=company.id,
        store_id=store.id if store else None,
        customer_id=customer.id,
        plan_version_id=plan_version.id,
        provider=BillingProvider.ASAAS,
        provider_subscription_id=provider_payload.get("id"),
        scope=plan_version.billing_scope,
        status=SubscriptionStatus.TRIALING if plan_version.trial_days else SubscriptionStatus.ACTIVE,
        billing_cycle=plan_version.billing_cycle,
        price_amount=amount,
        next_due_date=next_due_date,
        trial_ends_at=(
            datetime.now(timezone.utc) + timedelta(days=plan_version.trial_days)
            if plan_version.trial_days
            else None
        ),
        raw_payload=provider_payload,
    )
    session.add(subscription)
    await session.flush()

    await record_audit_log(
        session,
        action="billing.subscription_created",
        resource_type="subscription",
        actor_user_id=actor.user.id,
        resource_id=str(subscription.id),
        company_id=company.id,
        store_id=store.id if store else None,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"provider_subscription_id": subscription.provider_subscription_id},
    )
    await session.commit()
    return serialize_subscription(subscription)


@router.get("/subscriptions", response_model=list[SubscriptionRead])
async def list_subscriptions(
    company_id: UUID | None = Query(default=None),
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> list[SubscriptionRead]:
    stmt = select(Subscription).order_by(Subscription.created_at.desc())
    if company_id:
        if not (actor.is_superadmin or actor.has_permission("billing.view", company_id=company_id)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para billing desta empresa.")
        stmt = stmt.where(Subscription.company_id == company_id)
    elif not actor.is_superadmin:
        company_ids = list(actor.company_roles.keys())
        if not company_ids:
            return []
        stmt = stmt.where(Subscription.company_id.in_(company_ids))

    subscriptions = (await session.scalars(stmt)).all()
    return [serialize_subscription(item) for item in subscriptions]


@router.post("/subscriptions/{subscription_id}/cancel", response_model=SubscriptionRead)
async def cancel_subscription(
    subscription_id: UUID,
    request: Request,
    actor: CurrentActor = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db_session),
) -> SubscriptionRead:
    subscription = await session.get(Subscription, subscription_id)
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assinatura nao encontrada.")
    if subscription.provider_subscription_id:
        try:
            await AsaasClient().delete_subscription(subscription.provider_subscription_id)
        except BillingIntegrationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    subscription.status = SubscriptionStatus.CANCELED
    subscription.canceled_at = datetime.now(timezone.utc)
    await record_audit_log(
        session,
        action="billing.subscription_canceled",
        resource_type="subscription",
        actor_user_id=actor.user.id,
        resource_id=str(subscription.id),
        company_id=subscription.company_id,
        store_id=subscription.store_id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
    )
    await session.commit()
    return serialize_subscription(subscription)


@router.get("/companies/{company_id}/summary", response_model=CompanyBillingSummary)
async def company_billing_summary(
    company_id: UUID,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> CompanyBillingSummary:
    if not (actor.is_superadmin or actor.has_permission("billing.view", company_id=company_id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para billing desta empresa.")
    return await build_company_billing_summary(session, company_id=company_id)


@router.get("/invoices", response_model=list[InvoiceRead])
async def list_invoices(
    company_id: UUID,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> list[InvoiceRead]:
    if not (actor.is_superadmin or actor.has_permission("billing.view", company_id=company_id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para billing desta empresa.")
    invoices = (
        await session.scalars(
            select(Invoice)
            .where(Invoice.company_id == company_id)
            .order_by(Invoice.due_date.desc().nullslast(), Invoice.created_at.desc())
        )
    ).all()
    return [serialize_invoice(item) for item in invoices]


@router.get("/payments", response_model=list[PaymentRead])
async def list_payments(
    company_id: UUID,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> list[PaymentRead]:
    if not (actor.is_superadmin or actor.has_permission("billing.view", company_id=company_id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para billing desta empresa.")
    payments = (
        await session.scalars(
            select(Payment)
            .join(Invoice, Invoice.id == Payment.invoice_id)
            .where(Invoice.company_id == company_id)
            .order_by(Payment.paid_at.desc().nullslast(), Payment.created_at.desc())
        )
    ).all()
    return [serialize_payment(item) for item in payments]


@router.post("/providers/asaas/webhooks", response_model=BillingWebhookAck)
async def handle_asaas_webhook(
    request: Request,
    payload: dict,
    session: AsyncSession = Depends(get_db_session),
    asaas_access_token: str | None = Header(default=None, alias="asaas-access-token"),
) -> BillingWebhookAck:
    expected = settings.asaas_webhook_auth_token.strip()
    if expected and asaas_access_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Webhook Asaas nao autorizado.")
    event_type, provider_event_id, _, _ = derive_asaas_event_identity(payload)

    existing = None
    if provider_event_id:
        existing = await session.scalar(
            select(BillingProviderEvent).where(
                BillingProviderEvent.provider == BillingProvider.ASAAS,
                BillingProviderEvent.provider_event_id == provider_event_id,
            )
        )
    if existing:
        return BillingWebhookAck(
            message="Webhook ja recebido anteriormente.",
            event_id=existing.id,
            processing_status=existing.processing_status,
        )

    provider_event = BillingProviderEvent(
        provider=BillingProvider.ASAAS,
        provider_event_id=provider_event_id,
        event_type=event_type,
        headers={key: value for key, value in request.headers.items()},
        raw_payload=payload,
        processing_status="queued",
        processing_notes="Evento recebido e enfileirado.",
    )
    session.add(provider_event)
    await session.commit()

    try:
        enqueue_billing_provider_event(provider_event.id)
        return BillingWebhookAck(
            message="Webhook de billing enfileirado.",
            event_id=provider_event.id,
            processing_status=provider_event.processing_status,
        )
    except Exception as exc:
        provider_event.processing_status = "processing"
        provider_event.processing_notes = f"Fila indisponivel; executando fallback inline. {exc}"
        await session.flush()
        try:
            await process_asaas_webhook(session, payload, provider_event=provider_event)
        except Exception as inline_exc:
            provider_event.processing_status = "failed"
            provider_event.processing_notes = str(inline_exc)
            provider_event.processed_at = datetime.now(timezone.utc)
            await session.commit()
            raise
        await session.commit()
        return BillingWebhookAck(
            message="Webhook de billing processado em modo de contingencia.",
            event_id=provider_event.id,
            processing_status=provider_event.processing_status,
        )
