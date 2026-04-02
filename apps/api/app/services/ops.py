from datetime import datetime, timezone

from app.core.config import settings
from app.models.automation import AutomationExecution
from app.models.audit import AuditLog
from app.models.billing import BillingProviderEvent
from app.models.meta import WebhookEvent
from app.models.runtime import IncidentEvent, RestartEvent, StoreHealthCheck, StoreRuntimeState
from app.models.tenant import Store
from app.schemas.ops import (
    AutomationExecutionQueueRead,
    AuditLogRead,
    BillingProviderEventRead,
    IncidentRead,
    MetaWebhookQueueEventRead,
    RestartEventRead,
    RuntimeStateRead,
    StoreHealthCheckRead,
)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def heartbeat_age_seconds(last_heartbeat_at: datetime | None) -> int | None:
    if not last_heartbeat_at:
        return None
    return max(0, int((now_utc() - last_heartbeat_at).total_seconds()))


def compute_effective_status(
    *,
    store_status: str,
    runtime_state: StoreRuntimeState | None,
    degraded_channels: int = 0,
    unresolved_incidents: int = 0,
) -> str:
    if store_status == "suspended":
        return "suspended"
    if store_status != "active":
        return "offline"
    if runtime_state is None:
        return "offline"

    lifecycle = runtime_state.lifecycle_status.value
    if lifecycle == "restarting":
        return "restarting"
    if lifecycle == "suspended":
        return "suspended"

    age = heartbeat_age_seconds(runtime_state.last_heartbeat_at)
    if age is None or age > settings.store_heartbeat_stale_after_seconds:
        return "offline"

    if lifecycle == "degraded" or degraded_channels > 0 or unresolved_incidents > 0:
        return "degraded"
    return "online"


def serialize_runtime_state(state: StoreRuntimeState) -> RuntimeStateRead:
    return RuntimeStateRead(
        id=state.id,
        company_id=state.company_id,
        store_id=state.store_id,
        runtime_generation=state.runtime_generation,
        lifecycle_status=state.lifecycle_status.value,
        heartbeat_interval_seconds=state.heartbeat_interval_seconds,
        last_heartbeat_at=state.last_heartbeat_at,
        queue_depth=state.queue_depth,
        active_jobs=state.active_jobs,
        backlog_count=state.backlog_count,
        current_worker_shard=state.current_worker_shard,
        version=state.version,
        last_restart_requested_at=state.last_restart_requested_at,
        last_restart_started_at=state.last_restart_started_at,
        last_restart_completed_at=state.last_restart_completed_at,
        last_error_at=state.last_error_at,
        last_error_message=state.last_error_message,
        metadata=state.metadata_json,
        created_at=state.created_at,
        updated_at=state.updated_at,
    )


def serialize_health_check(item: StoreHealthCheck) -> StoreHealthCheckRead:
    return StoreHealthCheckRead(
        id=item.id,
        company_id=item.company_id,
        store_id=item.store_id,
        runtime_state_id=item.runtime_state_id,
        lifecycle_status=item.lifecycle_status.value,
        runtime_generation=item.runtime_generation,
        queue_depth=item.queue_depth,
        active_jobs=item.active_jobs,
        backlog_count=item.backlog_count,
        cpu_percent=float(item.cpu_percent) if item.cpu_percent is not None else None,
        memory_percent=float(item.memory_percent) if item.memory_percent is not None else None,
        observed_at=item.observed_at,
        metadata=item.metadata_json,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def serialize_incident(item: IncidentEvent) -> IncidentRead:
    return IncidentRead(
        id=item.id,
        company_id=item.company_id,
        store_id=item.store_id,
        severity=item.severity.value,
        source=item.source,
        title=item.title,
        message=item.message,
        is_resolved=item.is_resolved,
        resolved_at=item.resolved_at,
        resolved_by_user_id=item.resolved_by_user_id,
        occurred_at=item.occurred_at,
        metadata=item.metadata_json,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def serialize_restart(item: RestartEvent) -> RestartEventRead:
    return RestartEventRead(
        id=item.id,
        company_id=item.company_id,
        store_id=item.store_id,
        requested_by_user_id=item.requested_by_user_id,
        status=item.status.value,
        reason=item.reason,
        requested_at=item.requested_at,
        started_at=item.started_at,
        completed_at=item.completed_at,
        failure_message=item.failure_message,
        before_generation=item.before_generation,
        after_generation=item.after_generation,
        metadata=item.metadata_json,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def serialize_audit_log(item: AuditLog) -> AuditLogRead:
    return AuditLogRead(
        id=item.id,
        actor_user_id=item.actor_user_id,
        action=item.action,
        resource_type=item.resource_type,
        resource_id=item.resource_id,
        company_id=item.company_id,
        store_id=item.store_id,
        ip_address=item.ip_address,
        user_agent=item.user_agent,
        metadata=item.metadata_json,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def serialize_meta_webhook_event(item: WebhookEvent) -> MetaWebhookQueueEventRead:
    return MetaWebhookQueueEventRead(
        id=item.id,
        channel_id=item.channel_id,
        company_id=item.channel.company_id if item.channel else None,
        store_id=item.channel.store_id if item.channel else None,
        phone_number_id=item.phone_number_id,
        processing_status=item.processing_status,
        processing_notes=item.processing_notes,
        processing_attempts=item.processing_attempts,
        last_attempt_at=item.last_attempt_at,
        next_retry_at=item.next_retry_at,
        dead_lettered_at=item.dead_lettered_at,
        processed_at=item.processed_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def serialize_billing_provider_event(item: BillingProviderEvent) -> BillingProviderEventRead:
    return BillingProviderEventRead(
        id=item.id,
        company_id=item.company_id,
        subscription_id=item.subscription_id,
        invoice_id=item.invoice_id,
        provider_event_id=item.provider_event_id,
        event_type=item.event_type,
        processing_status=item.processing_status,
        processing_notes=item.processing_notes,
        processing_attempts=item.processing_attempts,
        last_attempt_at=item.last_attempt_at,
        next_retry_at=item.next_retry_at,
        dead_lettered_at=item.dead_lettered_at,
        processed_at=item.processed_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def resolve_automation_queue_status(item: AutomationExecution) -> str:
    if item.dead_lettered_at is not None:
        return "dead_lettered"
    if item.status.value == "failed" and item.next_retry_at is not None:
        return "retry_scheduled"
    return item.status.value


def serialize_automation_execution(item: AutomationExecution) -> AutomationExecutionQueueRead:
    return AutomationExecutionQueueRead(
        id=item.id,
        rule_id=item.rule_id,
        rule_name=item.rule.name if item.rule else "",
        company_id=item.company_id,
        store_id=item.store_id,
        channel_id=item.channel_id,
        conversation_id=item.conversation_id,
        requested_by_user_id=item.requested_by_user_id,
        requested_by_user_name=item.requested_by_user.full_name if item.requested_by_user else None,
        status=resolve_automation_queue_status(item),
        rendered_message=item.rendered_message,
        result_notes=item.result_notes,
        provider_message_id=item.provider_message_id,
        metadata=item.metadata_json,
        processing_attempts=item.processing_attempts,
        last_attempt_at=item.last_attempt_at,
        next_retry_at=item.next_retry_at,
        dead_lettered_at=item.dead_lettered_at,
        started_at=item.started_at,
        finished_at=item.finished_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def build_store_health_summary(
    *,
    store: Store,
    runtime_state: StoreRuntimeState | None,
    active_channels: int,
    degraded_channels: int,
    failed_webhooks_24h: int,
    failed_messages_24h: int,
    unresolved_incidents: int,
    pending_restarts: int,
    last_valid_event_at: datetime | None,
) -> dict:
    effective_status = compute_effective_status(
        store_status=store.status.value,
        runtime_state=runtime_state,
        degraded_channels=degraded_channels,
        unresolved_incidents=unresolved_incidents,
    )
    return {
        "store_id": store.id,
        "store_name": store.name,
        "company_id": store.company_id,
        "company_name": store.company.display_name,
        "store_status": store.status.value,
        "effective_status": effective_status,
        "runtime_generation": runtime_state.runtime_generation if runtime_state else 0,
        "heartbeat_age_seconds": heartbeat_age_seconds(runtime_state.last_heartbeat_at if runtime_state else None),
        "last_heartbeat_at": runtime_state.last_heartbeat_at if runtime_state else None,
        "last_valid_event_at": last_valid_event_at,
        "active_channels": active_channels,
        "degraded_channels": degraded_channels,
        "failed_webhooks_24h": failed_webhooks_24h,
        "failed_messages_24h": failed_messages_24h,
        "unresolved_incidents": unresolved_incidents,
        "pending_restarts": pending_restarts,
        "queue_depth": runtime_state.queue_depth if runtime_state else 0,
        "active_jobs": runtime_state.active_jobs if runtime_state else 0,
        "backlog_count": runtime_state.backlog_count if runtime_state else 0,
        "version": runtime_state.version if runtime_state else "",
        "last_error_at": runtime_state.last_error_at if runtime_state else None,
        "last_error_message": runtime_state.last_error_message if runtime_state else "",
    }
