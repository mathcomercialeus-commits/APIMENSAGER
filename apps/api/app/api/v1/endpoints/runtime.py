from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db_session
from app.models.enums import IncidentSeverity, RestartEventStatus, RuntimeLifecycleStatus
from app.models.runtime import IncidentEvent, RestartEvent, StoreHealthCheck, StoreRuntimeState
from app.models.tenant import Store
from app.schemas.common import MessageResponse
from app.schemas.ops import (
    IncidentRead,
    RestartEventRead,
    RuntimeHeartbeat,
    RuntimeIncidentCreate,
    RuntimeRestartAcknowledge,
    RuntimeStateRead,
)
from app.services.ops import serialize_incident, serialize_restart, serialize_runtime_state


router = APIRouter()


async def require_runtime_agent(x_runtime_token: str | None = Header(default=None)) -> str:
    configured = settings.runtime_agent_token.strip()
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Runtime agent token nao configurado.",
        )
    if x_runtime_token != configured:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Runtime token invalido.")
    return configured


async def _load_store(session: AsyncSession, store_id: UUID) -> Store | None:
    return await session.scalar(select(Store).where(Store.id == store_id))


async def _load_runtime_state(session: AsyncSession, store_id: UUID) -> StoreRuntimeState | None:
    return await session.scalar(select(StoreRuntimeState).where(StoreRuntimeState.store_id == store_id))


async def _load_restart_event(session: AsyncSession, restart_id: UUID, store_id: UUID) -> RestartEvent | None:
    return await session.scalar(
        select(RestartEvent).where(RestartEvent.id == restart_id, RestartEvent.store_id == store_id)
    )


@router.post("/stores/{store_id}/heartbeat", response_model=RuntimeStateRead)
async def store_heartbeat(
    store_id: UUID,
    payload: RuntimeHeartbeat,
    _: str = Depends(require_runtime_agent),
    session: AsyncSession = Depends(get_db_session),
) -> RuntimeStateRead:
    store = await _load_store(session, store_id)
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loja nao encontrada.")

    try:
        lifecycle_status = RuntimeLifecycleStatus(payload.lifecycle_status)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Status de runtime invalido.") from exc

    observed_at = payload.observed_at or datetime.now(timezone.utc)
    state = await _load_runtime_state(session, store.id)
    if state is None:
        state = StoreRuntimeState(
            company_id=store.company_id,
            store_id=store.id,
            runtime_generation=max(payload.runtime_generation, 1),
        )
        state.store = store
        session.add(state)
        await session.flush()

    state.runtime_generation = max(payload.runtime_generation, 1)
    state.lifecycle_status = lifecycle_status
    state.heartbeat_interval_seconds = payload.heartbeat_interval_seconds
    state.last_heartbeat_at = observed_at
    state.queue_depth = payload.queue_depth
    state.active_jobs = payload.active_jobs
    state.backlog_count = payload.backlog_count
    state.current_worker_shard = payload.current_worker_shard
    state.version = payload.version
    state.metadata_json = payload.metadata
    if lifecycle_status in {RuntimeLifecycleStatus.ONLINE, RuntimeLifecycleStatus.DEGRADED}:
        state.last_error_message = payload.metadata.get("last_error_message", state.last_error_message)

    health_check = StoreHealthCheck(
        company_id=store.company_id,
        store_id=store.id,
        runtime_state_id=state.id,
        lifecycle_status=lifecycle_status,
        runtime_generation=state.runtime_generation,
        queue_depth=payload.queue_depth,
        active_jobs=payload.active_jobs,
        backlog_count=payload.backlog_count,
        cpu_percent=payload.cpu_percent,
        memory_percent=payload.memory_percent,
        observed_at=observed_at,
        metadata_json=payload.metadata,
    )
    session.add(health_check)
    await session.commit()
    await session.refresh(state)
    return serialize_runtime_state(state)


@router.post("/stores/{store_id}/incidents", response_model=IncidentRead, status_code=status.HTTP_201_CREATED)
async def create_incident(
    store_id: UUID,
    payload: RuntimeIncidentCreate,
    _: str = Depends(require_runtime_agent),
    session: AsyncSession = Depends(get_db_session),
) -> IncidentRead:
    store = await _load_store(session, store_id)
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loja nao encontrada.")

    try:
        severity = IncidentSeverity(payload.severity)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Severidade invalida.") from exc

    incident = IncidentEvent(
        company_id=store.company_id,
        store_id=store.id,
        severity=severity,
        source=payload.source,
        title=payload.title,
        message=payload.message,
        occurred_at=payload.occurred_at or datetime.now(timezone.utc),
        metadata_json=payload.metadata,
    )
    session.add(incident)

    state = await _load_runtime_state(session, store.id)
    if state:
        state.last_error_at = incident.occurred_at
        state.last_error_message = payload.title if not payload.message else f"{payload.title}: {payload.message}"
        if severity in {IncidentSeverity.ERROR, IncidentSeverity.CRITICAL}:
            state.lifecycle_status = RuntimeLifecycleStatus.DEGRADED

    await session.commit()
    await session.refresh(incident)
    return serialize_incident(incident)


@router.post("/stores/{store_id}/restarts/{restart_id}/start", response_model=RestartEventRead)
async def start_restart(
    store_id: UUID,
    restart_id: UUID,
    _: str = Depends(require_runtime_agent),
    session: AsyncSession = Depends(get_db_session),
) -> RestartEventRead:
    restart_event = await _load_restart_event(session, restart_id, store_id)
    if not restart_event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evento de restart nao encontrado.")

    restart_event.status = RestartEventStatus.IN_PROGRESS
    restart_event.started_at = datetime.now(timezone.utc)

    state = await _load_runtime_state(session, store_id)
    if state:
        state.lifecycle_status = RuntimeLifecycleStatus.RESTARTING
        state.last_restart_started_at = restart_event.started_at

    await session.commit()
    await session.refresh(restart_event)
    return serialize_restart(restart_event)


@router.post("/stores/{store_id}/restarts/{restart_id}/complete", response_model=RestartEventRead)
async def complete_restart(
    store_id: UUID,
    restart_id: UUID,
    payload: RuntimeRestartAcknowledge,
    _: str = Depends(require_runtime_agent),
    session: AsyncSession = Depends(get_db_session),
) -> RestartEventRead:
    restart_event = await _load_restart_event(session, restart_id, store_id)
    if not restart_event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evento de restart nao encontrado.")

    finished_at = datetime.now(timezone.utc)
    restart_event.completed_at = finished_at
    restart_event.metadata_json = {**restart_event.metadata_json, **payload.metadata}

    state = await _load_runtime_state(session, store_id)
    if state:
        state.runtime_generation = restart_event.after_generation
        state.last_restart_completed_at = finished_at

    if payload.failure_message.strip():
        restart_event.status = RestartEventStatus.FAILED
        restart_event.failure_message = payload.failure_message.strip()
        if state:
            state.lifecycle_status = RuntimeLifecycleStatus.DEGRADED
            state.last_error_at = finished_at
            state.last_error_message = restart_event.failure_message
    else:
        restart_event.status = RestartEventStatus.COMPLETED
        if state:
            state.lifecycle_status = RuntimeLifecycleStatus.ONLINE
            state.last_error_message = ""

    await session.commit()
    await session.refresh(restart_event)
    return serialize_restart(restart_event)
