from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import and_, asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor, require_superadmin, request_ip
from app.core.database import get_db_session
from app.models.automation import AutomationExecution
from app.models.audit import AuditLog
from app.models.billing import BillingProviderEvent
from app.models.crm import ConversationMessage, WhatsAppChannel
from app.models.enums import (
    AutomationExecutionStatus,
    ChannelStatus,
    MessageDeliveryStatus,
    RestartEventStatus,
    RuntimeLifecycleStatus,
)
from app.models.meta import ChannelCredential, WebhookEvent
from app.models.runtime import IncidentEvent, RestartEvent, StoreHealthCheck, StoreRuntimeState
from app.models.tenant import Store
from app.schemas.common import MessageResponse
from app.schemas.ops import (
    AutomationExecutionQueuePageRead,
    AutomationExecutionQueueRead,
    AuditLogRead,
    BillingProviderEventPageRead,
    BillingProviderEventRead,
    IncidentRead,
    MetaWebhookQueuePageRead,
    MetaWebhookQueueEventRead,
    RestartEventRead,
    RestartRequest,
    StatusOverview,
    StoreHealthDetail,
    StoreHealthSummary,
)
from app.services.access import CurrentActor, get_store_or_404
from app.services.audit import record_audit_log
from app.services.ops import (
    build_store_health_summary,
    now_utc,
    resolve_automation_queue_status,
    serialize_automation_execution,
    serialize_audit_log,
    serialize_billing_provider_event,
    serialize_health_check,
    serialize_incident,
    serialize_meta_webhook_event,
    serialize_restart,
    serialize_runtime_state,
)
from app.workers.tasks import enqueue_automation_execution, enqueue_billing_provider_event, enqueue_meta_webhook_event


router = APIRouter()


def _status_count(counts: dict[str, int], *statuses: str) -> int:
    return sum(int(counts.get(status, 0)) for status in statuses)


def _parse_status_filter(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _apply_automation_status_filter(stmt, statuses: list[str]):
    if not statuses:
        return stmt

    clauses = []
    for item in statuses:
        if item == "retry_scheduled":
            clauses.append(
                and_(
                    AutomationExecution.status == AutomationExecutionStatus.FAILED,
                    AutomationExecution.next_retry_at.is_not(None),
                    AutomationExecution.dead_lettered_at.is_(None),
                )
            )
        elif item == "dead_lettered":
            clauses.append(AutomationExecution.dead_lettered_at.is_not(None))
        elif item == "failed":
            clauses.append(
                and_(
                    AutomationExecution.status == AutomationExecutionStatus.FAILED,
                    AutomationExecution.next_retry_at.is_(None),
                    AutomationExecution.dead_lettered_at.is_(None),
                )
            )
        elif item == "queued":
            clauses.append(AutomationExecution.status == AutomationExecutionStatus.QUEUED)
        elif item == "processing":
            clauses.append(AutomationExecution.status == AutomationExecutionStatus.PROCESSING)
        elif item == "executed":
            clauses.append(AutomationExecution.status == AutomationExecutionStatus.EXECUTED)
        elif item == "skipped":
            clauses.append(AutomationExecution.status == AutomationExecutionStatus.SKIPPED)

    if not clauses:
        return stmt.where(AutomationExecution.id.is_(None))
    return stmt.where(or_(*clauses))


def _apply_automation_ordering(stmt, order_by: str, order_direction: str):
    allowed_columns = {
        "created_at": AutomationExecution.created_at,
        "updated_at": AutomationExecution.updated_at,
        "started_at": AutomationExecution.started_at,
        "next_retry_at": AutomationExecution.next_retry_at,
        "processing_attempts": AutomationExecution.processing_attempts,
    }
    column = allowed_columns.get(order_by)
    if column is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ordenacao de automacao invalida.")
    if order_direction not in {"asc", "desc"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Direcao de ordenacao invalida.")
    ordering = asc(column) if order_direction == "asc" else desc(column)
    return stmt.order_by(ordering, desc(AutomationExecution.created_at))


def _apply_meta_queue_ordering(stmt, order_by: str, order_direction: str):
    allowed_columns = {
        "created_at": WebhookEvent.created_at,
        "updated_at": WebhookEvent.updated_at,
        "next_retry_at": WebhookEvent.next_retry_at,
        "processed_at": WebhookEvent.processed_at,
        "processing_attempts": WebhookEvent.processing_attempts,
    }
    column = allowed_columns.get(order_by)
    if column is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ordenacao de fila Meta invalida.")
    if order_direction not in {"asc", "desc"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Direcao de ordenacao invalida.")
    ordering = asc(column) if order_direction == "asc" else desc(column)
    return stmt.order_by(ordering, desc(WebhookEvent.created_at))


def _apply_billing_queue_ordering(stmt, order_by: str, order_direction: str):
    allowed_columns = {
        "created_at": BillingProviderEvent.created_at,
        "updated_at": BillingProviderEvent.updated_at,
        "next_retry_at": BillingProviderEvent.next_retry_at,
        "processed_at": BillingProviderEvent.processed_at,
        "processing_attempts": BillingProviderEvent.processing_attempts,
    }
    column = allowed_columns.get(order_by)
    if column is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ordenacao de fila billing invalida.")
    if order_direction not in {"asc", "desc"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Direcao de ordenacao invalida.")
    ordering = asc(column) if order_direction == "asc" else desc(column)
    return stmt.order_by(ordering, desc(BillingProviderEvent.created_at))


def _ensure_ops_view(actor: CurrentActor) -> None:
    if not actor.is_superadmin and "ops.view" not in actor.effective_permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para visualizar operacao.")


def _ensure_audit_view(actor: CurrentActor) -> None:
    if not actor.is_superadmin and "audit.view" not in actor.effective_permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para visualizar auditoria.")


def _apply_store_scope(stmt, actor: CurrentActor, *, company_id: UUID | None = None, store_id: UUID | None = None):
    if store_id:
        if not actor.can_access_store(store_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem acesso a esta loja.")
        return stmt.where(Store.id == store_id)

    if company_id:
        if not actor.can_access_company(company_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem acesso a esta empresa.")
        if actor.is_superadmin or company_id in actor.company_roles:
            return stmt.where(Store.company_id == company_id)
        scoped_store_ids = [item for item, mapped_company_id in actor.store_to_company.items() if mapped_company_id == company_id]
        if not scoped_store_ids:
            return stmt.where(Store.id.is_(None))
        return stmt.where(Store.company_id == company_id, Store.id.in_(scoped_store_ids))

    if actor.is_superadmin:
        return stmt

    company_ids = list(actor.company_roles.keys())
    store_ids = list(actor.store_roles.keys())
    if company_ids and store_ids:
        return stmt.where(or_(Store.company_id.in_(company_ids), Store.id.in_(store_ids)))
    if company_ids:
        return stmt.where(Store.company_id.in_(company_ids))
    if store_ids:
        return stmt.where(Store.id.in_(store_ids))
    return stmt.where(Store.id.is_(None))


def _count_channels_for_store(rows: list[tuple]) -> tuple[int, int]:
    active = 0
    degraded = 0
    for _, channel_status, credential_active, credential_error_at in rows:
        is_channel_active = channel_status == ChannelStatus.ACTIVE
        is_credential_active = credential_active is not False
        has_credential_error = credential_error_at is not None
        if is_channel_active and is_credential_active and not has_credential_error:
            active += 1
        else:
            degraded += 1
    return active, degraded


async def _load_store_health_maps(session: AsyncSession, store_ids: list[UUID]) -> dict[str, dict]:
    if not store_ids:
        return {
            "runtime": {},
            "channels": {},
            "webhooks": {},
            "messages": {},
            "incidents": {},
            "restarts": {},
            "last_webhook": {},
            "last_message": {},
        }

    runtime_rows = (
        await session.scalars(select(StoreRuntimeState).where(StoreRuntimeState.store_id.in_(store_ids)))
    ).all()
    runtime_map = {item.store_id: item for item in runtime_rows}

    channel_rows = (
        await session.execute(
            select(
                WhatsAppChannel.store_id,
                WhatsAppChannel.status,
                ChannelCredential.is_active,
                ChannelCredential.last_error_at,
            )
            .outerjoin(ChannelCredential, ChannelCredential.channel_id == WhatsAppChannel.id)
            .where(WhatsAppChannel.store_id.in_(store_ids))
        )
    ).all()
    channels_map: dict[UUID, list[tuple]] = {}
    for row in channel_rows:
        channels_map.setdefault(row.store_id, []).append(row)

    cutoff = now_utc() - timedelta(hours=24)
    failed_webhooks = dict(
        (
            await session.execute(
                select(WhatsAppChannel.store_id, func.count(WebhookEvent.id))
                .join(WebhookEvent, WebhookEvent.channel_id == WhatsAppChannel.id)
                .where(
                    WhatsAppChannel.store_id.in_(store_ids),
                    WebhookEvent.processing_status == "failed",
                    WebhookEvent.created_at >= cutoff,
                )
                .group_by(WhatsAppChannel.store_id)
            )
        ).all()
    )
    failed_messages = dict(
        (
            await session.execute(
                select(ConversationMessage.store_id, func.count(ConversationMessage.id))
                .where(
                    ConversationMessage.store_id.in_(store_ids),
                    ConversationMessage.delivery_status == MessageDeliveryStatus.FAILED,
                    ConversationMessage.created_at >= cutoff,
                )
                .group_by(ConversationMessage.store_id)
            )
        ).all()
    )
    unresolved_incidents = dict(
        (
            await session.execute(
                select(IncidentEvent.store_id, func.count(IncidentEvent.id))
                .where(
                    IncidentEvent.store_id.in_(store_ids),
                    IncidentEvent.is_resolved.is_(False),
                )
                .group_by(IncidentEvent.store_id)
            )
        ).all()
    )
    pending_restarts = dict(
        (
            await session.execute(
                select(RestartEvent.store_id, func.count(RestartEvent.id))
                .where(
                    RestartEvent.store_id.in_(store_ids),
                    RestartEvent.status.in_([RestartEventStatus.REQUESTED, RestartEventStatus.IN_PROGRESS]),
                )
                .group_by(RestartEvent.store_id)
            )
        ).all()
    )
    last_webhook = dict(
        (
            await session.execute(
                select(WhatsAppChannel.store_id, func.max(WebhookEvent.processed_at))
                .join(WebhookEvent, WebhookEvent.channel_id == WhatsAppChannel.id)
                .where(
                    WhatsAppChannel.store_id.in_(store_ids),
                    WebhookEvent.processing_status == "processed",
                )
                .group_by(WhatsAppChannel.store_id)
            )
        ).all()
    )
    last_message = dict(
        (
            await session.execute(
                select(ConversationMessage.store_id, func.max(ConversationMessage.sent_at))
                .where(ConversationMessage.store_id.in_(store_ids))
                .group_by(ConversationMessage.store_id)
            )
        ).all()
    )

    return {
        "runtime": runtime_map,
        "channels": channels_map,
        "webhooks": {key: int(value or 0) for key, value in failed_webhooks.items()},
        "messages": {key: int(value or 0) for key, value in failed_messages.items()},
        "incidents": {key: int(value or 0) for key, value in unresolved_incidents.items()},
        "restarts": {key: int(value or 0) for key, value in pending_restarts.items()},
        "last_webhook": last_webhook,
        "last_message": last_message,
    }


def _latest_timestamp(first: datetime | None, second: datetime | None) -> datetime | None:
    if first and second:
        return max(first, second)
    return first or second


async def _build_store_summaries(
    session: AsyncSession,
    stores: list[Store],
) -> list[StoreHealthSummary]:
    store_ids = [item.id for item in stores]
    maps = await _load_store_health_maps(session, store_ids)
    summaries: list[StoreHealthSummary] = []
    for store in stores:
        runtime_state = maps["runtime"].get(store.id)
        active_channels, degraded_channels = _count_channels_for_store(maps["channels"].get(store.id, []))
        last_valid_event_at = _latest_timestamp(
            maps["last_webhook"].get(store.id),
            maps["last_message"].get(store.id),
        )
        summary = build_store_health_summary(
            store=store,
            runtime_state=runtime_state,
            active_channels=active_channels,
            degraded_channels=degraded_channels,
            failed_webhooks_24h=maps["webhooks"].get(store.id, 0),
            failed_messages_24h=maps["messages"].get(store.id, 0),
            unresolved_incidents=maps["incidents"].get(store.id, 0),
            pending_restarts=maps["restarts"].get(store.id, 0),
            last_valid_event_at=last_valid_event_at,
        )
        summaries.append(StoreHealthSummary(**summary))
    return summaries


@router.get("/status/overview", response_model=StatusOverview)
async def status_overview(
    company_id: UUID | None = Query(default=None),
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> StatusOverview:
    _ensure_ops_view(actor)
    stmt = select(Store).order_by(Store.name)
    stmt = _apply_store_scope(stmt, actor, company_id=company_id)
    stores = (await session.scalars(stmt)).all()
    summaries = await _build_store_summaries(session, stores)
    company_scope = {item.company_id for item in summaries}

    meta_status_stmt = select(WebhookEvent.processing_status, func.count(WebhookEvent.id)).group_by(WebhookEvent.processing_status)
    billing_status_stmt = (
        select(BillingProviderEvent.processing_status, func.count(BillingProviderEvent.id))
        .group_by(BillingProviderEvent.processing_status)
    )
    automation_status_stmt = select(
        func.count(AutomationExecution.id).filter(AutomationExecution.status == AutomationExecutionStatus.QUEUED),
        func.count(AutomationExecution.id).filter(AutomationExecution.status == AutomationExecutionStatus.PROCESSING),
        func.count(AutomationExecution.id).filter(
            and_(
                AutomationExecution.status == AutomationExecutionStatus.FAILED,
                AutomationExecution.next_retry_at.is_not(None),
                AutomationExecution.dead_lettered_at.is_(None),
            )
        ),
        func.count(AutomationExecution.id).filter(AutomationExecution.dead_lettered_at.is_not(None)),
        func.count(AutomationExecution.id).filter(AutomationExecution.status == AutomationExecutionStatus.SKIPPED),
        func.count(AutomationExecution.id).filter(
            or_(
                AutomationExecution.status == AutomationExecutionStatus.FAILED,
                AutomationExecution.dead_lettered_at.is_not(None),
            )
        ),
    )
    if company_id:
        meta_status_stmt = meta_status_stmt.join(WhatsAppChannel, WebhookEvent.channel_id == WhatsAppChannel.id).where(
            WhatsAppChannel.company_id == company_id
        )
        billing_status_stmt = billing_status_stmt.where(BillingProviderEvent.company_id == company_id)
        automation_status_stmt = automation_status_stmt.where(AutomationExecution.company_id == company_id)
    elif not actor.is_superadmin:
        if company_scope:
            meta_status_stmt = meta_status_stmt.join(WhatsAppChannel, WebhookEvent.channel_id == WhatsAppChannel.id).where(
                WhatsAppChannel.company_id.in_(company_scope)
            )
            billing_status_stmt = billing_status_stmt.where(BillingProviderEvent.company_id.in_(company_scope))
            automation_status_stmt = automation_status_stmt.where(AutomationExecution.company_id.in_(company_scope))
        else:
            meta_status_stmt = meta_status_stmt.where(WebhookEvent.id.is_(None))
            billing_status_stmt = billing_status_stmt.where(BillingProviderEvent.id.is_(None))
            automation_status_stmt = automation_status_stmt.where(AutomationExecution.id.is_(None))

    meta_status_counts = dict((await session.execute(meta_status_stmt)).all())
    billing_status_counts = dict((await session.execute(billing_status_stmt)).all())
    automation_status_row = (await session.execute(automation_status_stmt)).one()

    return StatusOverview(
        total_companies=len({item.company_id for item in summaries}),
        total_stores=len(summaries),
        online_stores=sum(1 for item in summaries if item.effective_status == "online"),
        degraded_stores=sum(1 for item in summaries if item.effective_status == "degraded"),
        offline_stores=sum(1 for item in summaries if item.effective_status == "offline"),
        restarting_stores=sum(1 for item in summaries if item.effective_status == "restarting"),
        suspended_stores=sum(1 for item in summaries if item.effective_status == "suspended"),
        failed_webhooks_24h=sum(item.failed_webhooks_24h for item in summaries),
        failed_messages_24h=sum(item.failed_messages_24h for item in summaries),
        unresolved_incidents=sum(item.unresolved_incidents for item in summaries),
        pending_restarts=sum(item.pending_restarts for item in summaries),
        queued_meta_webhooks=_status_count(meta_status_counts, "queued"),
        processing_meta_webhooks=int(meta_status_counts.get("processing", 0)),
        retry_scheduled_meta_webhooks=int(meta_status_counts.get("retry_scheduled", 0)),
        dead_lettered_meta_webhooks=int(meta_status_counts.get("dead_lettered", 0)),
        failed_meta_webhooks_total=_status_count(meta_status_counts, "failed", "dead_lettered"),
        queued_billing_events=_status_count(billing_status_counts, "queued"),
        processing_billing_events=int(billing_status_counts.get("processing", 0)),
        retry_scheduled_billing_events=int(billing_status_counts.get("retry_scheduled", 0)),
        dead_lettered_billing_events=int(billing_status_counts.get("dead_lettered", 0)),
        failed_billing_events_total=_status_count(billing_status_counts, "failed", "dead_lettered"),
        queued_automation_executions=int(automation_status_row[0] or 0),
        processing_automation_executions=int(automation_status_row[1] or 0),
        retry_scheduled_automation_executions=int(automation_status_row[2] or 0),
        dead_lettered_automation_executions=int(automation_status_row[3] or 0),
        skipped_automation_executions=int(automation_status_row[4] or 0),
        failed_automation_executions_total=int(automation_status_row[5] or 0),
    )


@router.get("/stores/health", response_model=list[StoreHealthSummary])
async def list_store_health(
    company_id: UUID | None = Query(default=None),
    store_id: UUID | None = Query(default=None),
    effective_status: str | None = Query(default=None),
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> list[StoreHealthSummary]:
    _ensure_ops_view(actor)
    stmt = select(Store).order_by(Store.name)
    stmt = _apply_store_scope(stmt, actor, company_id=company_id, store_id=store_id)
    stores = (await session.scalars(stmt)).all()
    summaries = await _build_store_summaries(session, stores)
    if effective_status:
        summaries = [item for item in summaries if item.effective_status == effective_status]
    return summaries


@router.get("/stores/{store_id}/health", response_model=StoreHealthDetail)
async def get_store_health(
    store_id: UUID,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> StoreHealthDetail:
    store = await get_store_or_404(session, store_id)
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loja nao encontrada.")
    if not actor.has_permission("ops.view", company_id=store.company_id, store_id=store.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem acesso ao status desta loja.")

    summary = (await _build_store_summaries(session, [store]))[0]
    runtime_state = await session.scalar(select(StoreRuntimeState).where(StoreRuntimeState.store_id == store.id))
    health_checks = (
        await session.scalars(
            select(StoreHealthCheck)
            .where(StoreHealthCheck.store_id == store.id)
            .order_by(StoreHealthCheck.observed_at.desc())
            .limit(20)
        )
    ).all()
    incidents = (
        await session.scalars(
            select(IncidentEvent)
            .where(IncidentEvent.store_id == store.id)
            .order_by(IncidentEvent.occurred_at.desc(), IncidentEvent.created_at.desc())
            .limit(20)
        )
    ).all()
    restarts = (
        await session.scalars(
            select(RestartEvent)
            .where(RestartEvent.store_id == store.id)
            .order_by(RestartEvent.requested_at.desc(), RestartEvent.created_at.desc())
            .limit(20)
        )
    ).all()

    return StoreHealthDetail(
        **summary.model_dump(),
        runtime_state=serialize_runtime_state(runtime_state) if runtime_state else None,
        recent_health_checks=[serialize_health_check(item) for item in health_checks],
        recent_incidents=[serialize_incident(item) for item in incidents],
        recent_restarts=[serialize_restart(item) for item in restarts],
    )


@router.post("/stores/{store_id}/restart", response_model=RestartEventRead, status_code=status.HTTP_202_ACCEPTED)
async def request_store_restart(
    store_id: UUID,
    payload: RestartRequest,
    request: Request,
    actor: CurrentActor = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db_session),
) -> RestartEventRead:
    store = await get_store_or_404(session, store_id)
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loja nao encontrada.")

    runtime_state = await session.scalar(select(StoreRuntimeState).where(StoreRuntimeState.store_id == store.id))
    if runtime_state is None:
        runtime_state = StoreRuntimeState(
            company_id=store.company_id,
            store_id=store.id,
            runtime_generation=1,
            lifecycle_status=RuntimeLifecycleStatus.OFFLINE,
        )
        runtime_state.store = store
        session.add(runtime_state)
        await session.flush()

    before_generation = runtime_state.runtime_generation
    after_generation = before_generation + 1
    requested_at = now_utc()
    runtime_state.runtime_generation = after_generation
    runtime_state.lifecycle_status = RuntimeLifecycleStatus.RESTARTING
    runtime_state.last_restart_requested_at = requested_at

    restart_event = RestartEvent(
        company_id=store.company_id,
        store_id=store.id,
        requested_by_user_id=actor.user.id,
        status=RestartEventStatus.REQUESTED,
        reason=payload.reason,
        requested_at=requested_at,
        before_generation=before_generation,
        after_generation=after_generation,
        metadata_json=payload.metadata,
    )
    session.add(restart_event)
    await session.flush()

    await record_audit_log(
        session,
        action="ops.store_restart_requested",
        resource_type="restart_event",
        actor_user_id=actor.user.id,
        resource_id=str(restart_event.id),
        company_id=store.company_id,
        store_id=store.id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={
            "before_generation": before_generation,
            "after_generation": after_generation,
            "reason": payload.reason,
        },
    )
    await session.commit()
    await session.refresh(restart_event)
    return serialize_restart(restart_event)


@router.get("/restarts", response_model=list[RestartEventRead])
async def list_restarts(
    company_id: UUID | None = Query(default=None),
    store_id: UUID | None = Query(default=None),
    restart_status: str | None = Query(default=None, alias="status"),
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> list[RestartEventRead]:
    _ensure_ops_view(actor)
    stmt = select(RestartEvent).order_by(RestartEvent.requested_at.desc(), RestartEvent.created_at.desc())
    if store_id:
        store = await get_store_or_404(session, store_id)
        if not store:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loja nao encontrada.")
        if not actor.has_permission("ops.view", company_id=store.company_id, store_id=store.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem acesso a esta loja.")
        stmt = stmt.where(RestartEvent.store_id == store.id)
    elif company_id:
        stmt = _apply_store_scope(select(Store), actor, company_id=company_id)
        allowed_stores = (await session.scalars(stmt)).all()
        allowed_ids = [item.id for item in allowed_stores]
        if not allowed_ids:
            return []
        stmt = select(RestartEvent).where(RestartEvent.store_id.in_(allowed_ids)).order_by(RestartEvent.requested_at.desc(), RestartEvent.created_at.desc())
    elif not actor.is_superadmin:
        scoped_stmt = _apply_store_scope(select(Store), actor)
        allowed_stores = (await session.scalars(scoped_stmt)).all()
        allowed_ids = [item.id for item in allowed_stores]
        if not allowed_ids:
            return []
        stmt = stmt.where(RestartEvent.store_id.in_(allowed_ids))

    if restart_status:
        try:
            status_value = RestartEventStatus(restart_status)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Status de restart invalido.") from exc
        stmt = stmt.where(RestartEvent.status == status_value)

    restarts = (await session.scalars(stmt)).all()
    return [serialize_restart(item) for item in restarts]


@router.get("/queue/meta-webhooks", response_model=MetaWebhookQueuePageRead)
async def list_meta_webhook_queue(
    company_id: UUID | None = Query(default=None),
    store_id: UUID | None = Query(default=None),
    status_filter: str | None = Query(default="retry_scheduled,dead_lettered", alias="status"),
    limit: int = Query(default=10, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=5000),
    order_by: str = Query(default="updated_at"),
    order_direction: str = Query(default="desc"),
    _: CurrentActor = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db_session),
) -> MetaWebhookQueuePageRead:
    stmt = select(WebhookEvent)
    if company_id or store_id:
        stmt = stmt.join(WhatsAppChannel, WebhookEvent.channel_id == WhatsAppChannel.id)
        if company_id:
            stmt = stmt.where(WhatsAppChannel.company_id == company_id)
        if store_id:
            stmt = stmt.where(WhatsAppChannel.store_id == store_id)
    statuses = _parse_status_filter(status_filter)
    if statuses:
        stmt = stmt.where(WebhookEvent.processing_status.in_(statuses))
    total_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = int((await session.scalar(total_stmt)) or 0)
    stmt = _apply_meta_queue_ordering(stmt, order_by, order_direction)
    events = (await session.scalars(stmt.offset(offset).limit(limit))).all()
    return MetaWebhookQueuePageRead(
        items=[serialize_meta_webhook_event(item) for item in events],
        total=total,
        limit=limit,
        offset=offset,
        order_by=order_by,
        order_direction=order_direction,
    )


@router.post("/queue/meta-webhooks/{event_id}/requeue", response_model=MetaWebhookQueueEventRead)
async def requeue_meta_webhook(
    event_id: UUID,
    request: Request,
    actor: CurrentActor = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db_session),
) -> MetaWebhookQueueEventRead:
    event = await session.get(WebhookEvent, event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evento Meta nao encontrado.")
    if event.processing_status == "processing":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Evento ainda esta em processamento.")

    previous_attempts = event.processing_attempts
    event.processing_status = "queued"
    event.processing_notes = "Evento reenfileirado manualmente pelo superadmin."
    event.processing_attempts = 0
    event.last_attempt_at = None
    event.next_retry_at = None
    event.dead_lettered_at = None
    event.processed_at = None
    await session.commit()
    try:
        enqueue_meta_webhook_event(event.id)
    except Exception as exc:
        event.processing_notes = f"Falha ao reenfileirar manualmente: {exc}"
        await session.commit()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Fila indisponivel para reenfileirar o evento.") from exc
    await record_audit_log(
        session,
        action="ops.meta_webhook_requeued",
        resource_type="webhook_event",
        actor_user_id=actor.user.id,
        resource_id=str(event.id),
        company_id=event.channel.company_id if event.channel else None,
        store_id=event.channel.store_id if event.channel else None,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"previous_attempts": previous_attempts},
    )
    await session.commit()
    await session.refresh(event)
    return serialize_meta_webhook_event(event)


@router.get("/queue/billing-events", response_model=BillingProviderEventPageRead)
async def list_billing_queue(
    status_filter: str | None = Query(default="retry_scheduled,dead_lettered", alias="status"),
    limit: int = Query(default=10, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=5000),
    order_by: str = Query(default="updated_at"),
    order_direction: str = Query(default="desc"),
    _: CurrentActor = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db_session),
) -> BillingProviderEventPageRead:
    stmt = select(BillingProviderEvent)
    statuses = _parse_status_filter(status_filter)
    if statuses:
        stmt = stmt.where(BillingProviderEvent.processing_status.in_(statuses))
    total_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = int((await session.scalar(total_stmt)) or 0)
    stmt = _apply_billing_queue_ordering(stmt, order_by, order_direction)
    events = (await session.scalars(stmt.offset(offset).limit(limit))).all()
    return BillingProviderEventPageRead(
        items=[serialize_billing_provider_event(item) for item in events],
        total=total,
        limit=limit,
        offset=offset,
        order_by=order_by,
        order_direction=order_direction,
    )


@router.get("/queue/automation-executions", response_model=AutomationExecutionQueuePageRead)
async def list_automation_queue(
    company_id: UUID | None = Query(default=None),
    store_id: UUID | None = Query(default=None),
    rule_id: UUID | None = Query(default=None),
    channel_id: UUID | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    status_filter: str | None = Query(default="processing,retry_scheduled,dead_lettered,skipped", alias="status"),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=5000),
    order_by: str = Query(default="created_at"),
    order_direction: str = Query(default="desc"),
    _: CurrentActor = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db_session),
) -> AutomationExecutionQueuePageRead:
    stmt = select(AutomationExecution)
    if company_id:
        stmt = stmt.where(AutomationExecution.company_id == company_id)
    if store_id:
        stmt = stmt.where(AutomationExecution.store_id == store_id)
    if rule_id:
        stmt = stmt.where(AutomationExecution.rule_id == rule_id)
    if channel_id:
        stmt = stmt.where(AutomationExecution.channel_id == channel_id)
    if created_from:
        stmt = stmt.where(AutomationExecution.created_at >= created_from)
    if created_to:
        stmt = stmt.where(AutomationExecution.created_at <= created_to)
    statuses = _parse_status_filter(status_filter)
    stmt = _apply_automation_status_filter(stmt, statuses)
    total_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = int((await session.scalar(total_stmt)) or 0)
    stmt = _apply_automation_ordering(stmt, order_by, order_direction)
    items = (await session.scalars(stmt.offset(offset).limit(limit))).all()
    return AutomationExecutionQueuePageRead(
        items=[serialize_automation_execution(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
        order_by=order_by,
        order_direction=order_direction,
    )


@router.post("/queue/automation-executions/{execution_id}/requeue", response_model=AutomationExecutionQueueRead)
async def requeue_automation_execution_endpoint(
    execution_id: UUID,
    request: Request,
    actor: CurrentActor = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db_session),
) -> AutomationExecutionQueueRead:
    execution = await session.get(AutomationExecution, execution_id)
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execucao de automacao nao encontrada.")
    if execution.status.value == "processing":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Execucao ainda esta em processamento.")

    previous_status = execution.status.value
    execution.status = AutomationExecutionStatus.QUEUED
    execution.result_notes = "Execucao reenfileirada manualmente pelo superadmin."
    execution.provider_message_id = ""
    execution.provider_response = {}
    execution.processing_attempts = 0
    execution.last_attempt_at = None
    execution.next_retry_at = None
    execution.dead_lettered_at = None
    execution.started_at = None
    execution.finished_at = None
    await session.commit()
    try:
        enqueue_automation_execution(execution.id)
    except Exception as exc:
        execution.status = AutomationExecutionStatus.FAILED
        execution.result_notes = f"Falha ao reenfileirar manualmente: {exc}"
        execution.finished_at = now_utc()
        await session.commit()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Fila indisponivel para reenfileirar a automacao.") from exc
    await record_audit_log(
        session,
        action="ops.automation_execution_requeued",
        resource_type="automation_execution",
        actor_user_id=actor.user.id,
        resource_id=str(execution.id),
        company_id=execution.company_id,
        store_id=execution.store_id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"previous_status": previous_status, "rule_id": str(execution.rule_id)},
    )
    await session.commit()
    await session.refresh(execution)
    return serialize_automation_execution(execution)


@router.post("/queue/billing-events/{event_id}/requeue", response_model=BillingProviderEventRead)
async def requeue_billing_event(
    event_id: UUID,
    request: Request,
    actor: CurrentActor = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db_session),
) -> BillingProviderEventRead:
    event = await session.get(BillingProviderEvent, event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evento de billing nao encontrado.")
    if event.processing_status == "processing":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Evento ainda esta em processamento.")

    previous_attempts = event.processing_attempts
    event.processing_status = "queued"
    event.processing_notes = "Evento de billing reenfileirado manualmente pelo superadmin."
    event.processing_attempts = 0
    event.last_attempt_at = None
    event.next_retry_at = None
    event.dead_lettered_at = None
    event.processed_at = None
    await session.commit()
    try:
        enqueue_billing_provider_event(event.id)
    except Exception as exc:
        event.processing_notes = f"Falha ao reenfileirar manualmente: {exc}"
        await session.commit()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Fila indisponivel para reenfileirar o evento.") from exc
    await record_audit_log(
        session,
        action="ops.billing_event_requeued",
        resource_type="billing_provider_event",
        actor_user_id=actor.user.id,
        resource_id=str(event.id),
        company_id=event.company_id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"previous_attempts": previous_attempts, "event_type": event.event_type},
    )
    await session.commit()
    await session.refresh(event)
    return serialize_billing_provider_event(event)


@router.post("/incidents/{incident_id}/resolve", response_model=IncidentRead)
async def resolve_incident(
    incident_id: UUID,
    request: Request,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> IncidentRead:
    incident = await session.get(IncidentEvent, incident_id)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incidente nao encontrado.")
    if not actor.has_permission("ops.view", company_id=incident.company_id, store_id=incident.store_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para resolver este incidente.")

    incident.is_resolved = True
    incident.resolved_at = now_utc()
    incident.resolved_by_user_id = actor.user.id

    await record_audit_log(
        session,
        action="ops.incident_resolved",
        resource_type="incident_event",
        actor_user_id=actor.user.id,
        resource_id=str(incident.id),
        company_id=incident.company_id,
        store_id=incident.store_id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"severity": incident.severity.value, "source": incident.source},
    )
    await session.commit()
    await session.refresh(incident)
    return serialize_incident(incident)


@router.get("/audit-logs", response_model=list[AuditLogRead])
async def list_audit_logs(
    company_id: UUID | None = Query(default=None),
    store_id: UUID | None = Query(default=None),
    action: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> list[AuditLogRead]:
    _ensure_audit_view(actor)
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if store_id:
        store = await get_store_or_404(session, store_id)
        if not store:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loja nao encontrada.")
        if not actor.has_permission("audit.view", company_id=store.company_id, store_id=store.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem acesso a auditoria desta loja.")
        stmt = stmt.where(AuditLog.store_id == store.id)
    elif company_id:
        if not (actor.is_superadmin or actor.has_permission("audit.view", company_id=company_id)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem acesso a auditoria desta empresa.")
        stmt = stmt.where(AuditLog.company_id == company_id)
    elif not actor.is_superadmin:
        company_ids = list(actor.company_roles.keys())
        store_ids = list(actor.store_roles.keys())
        if company_ids and store_ids:
            stmt = stmt.where(or_(AuditLog.company_id.in_(company_ids), AuditLog.store_id.in_(store_ids)))
        elif company_ids:
            stmt = stmt.where(AuditLog.company_id.in_(company_ids))
        elif store_ids:
            stmt = stmt.where(AuditLog.store_id.in_(store_ids))
        else:
            return []

    if action:
        stmt = stmt.where(AuditLog.action == action)

    items = (await session.scalars(stmt.limit(limit))).all()
    return [serialize_audit_log(item) for item in items]
