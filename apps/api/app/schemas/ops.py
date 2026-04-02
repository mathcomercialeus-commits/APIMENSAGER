from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from app.schemas.common import APIModel


class RuntimeHeartbeat(APIModel):
    runtime_generation: int
    lifecycle_status: str
    heartbeat_interval_seconds: int = 60
    queue_depth: int = 0
    active_jobs: int = 0
    backlog_count: int = 0
    current_worker_shard: str = ""
    version: str = ""
    cpu_percent: float | None = None
    memory_percent: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    observed_at: datetime | None = None


class RuntimeIncidentCreate(APIModel):
    severity: str
    source: str = "runtime"
    title: str
    message: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None


class RuntimeRestartAcknowledge(APIModel):
    failure_message: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuntimeStateRead(APIModel):
    id: UUID
    company_id: UUID
    store_id: UUID
    runtime_generation: int
    lifecycle_status: str
    heartbeat_interval_seconds: int
    last_heartbeat_at: datetime | None
    queue_depth: int
    active_jobs: int
    backlog_count: int
    current_worker_shard: str
    version: str
    last_restart_requested_at: datetime | None
    last_restart_started_at: datetime | None
    last_restart_completed_at: datetime | None
    last_error_at: datetime | None
    last_error_message: str
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class StoreHealthCheckRead(APIModel):
    id: UUID
    company_id: UUID
    store_id: UUID
    runtime_state_id: UUID | None
    lifecycle_status: str
    runtime_generation: int
    queue_depth: int
    active_jobs: int
    backlog_count: int
    cpu_percent: float | None
    memory_percent: float | None
    observed_at: datetime
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class IncidentRead(APIModel):
    id: UUID
    company_id: UUID
    store_id: UUID
    severity: str
    source: str
    title: str
    message: str
    is_resolved: bool
    resolved_at: datetime | None
    resolved_by_user_id: UUID | None
    occurred_at: datetime
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class RestartRequest(APIModel):
    reason: str = Field(min_length=3, max_length=2000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RestartEventRead(APIModel):
    id: UUID
    company_id: UUID
    store_id: UUID
    requested_by_user_id: UUID | None
    status: str
    reason: str
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    failure_message: str
    before_generation: int
    after_generation: int
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AuditLogRead(APIModel):
    id: UUID
    actor_user_id: UUID | None
    action: str
    resource_type: str
    resource_id: str
    company_id: UUID | None
    store_id: UUID | None
    ip_address: str
    user_agent: str
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class MetaWebhookQueueEventRead(APIModel):
    id: UUID
    channel_id: UUID | None
    company_id: UUID | None
    store_id: UUID | None
    phone_number_id: str
    processing_status: str
    processing_notes: str
    processing_attempts: int
    last_attempt_at: datetime | None
    next_retry_at: datetime | None
    dead_lettered_at: datetime | None
    processed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MetaWebhookQueuePageRead(APIModel):
    items: list[MetaWebhookQueueEventRead]
    total: int
    limit: int
    offset: int
    order_by: str
    order_direction: str


class BillingProviderEventRead(APIModel):
    id: UUID
    company_id: UUID | None
    subscription_id: UUID | None
    invoice_id: UUID | None
    provider_event_id: str | None
    event_type: str
    processing_status: str
    processing_notes: str
    processing_attempts: int
    last_attempt_at: datetime | None
    next_retry_at: datetime | None
    dead_lettered_at: datetime | None
    processed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class BillingProviderEventPageRead(APIModel):
    items: list[BillingProviderEventRead]
    total: int
    limit: int
    offset: int
    order_by: str
    order_direction: str


class AutomationExecutionQueueRead(APIModel):
    id: UUID
    rule_id: UUID
    rule_name: str
    company_id: UUID
    store_id: UUID
    channel_id: UUID | None
    conversation_id: UUID | None
    requested_by_user_id: UUID | None
    requested_by_user_name: str | None
    status: str
    rendered_message: str
    result_notes: str
    provider_message_id: str
    metadata: dict[str, Any]
    processing_attempts: int
    last_attempt_at: datetime | None
    next_retry_at: datetime | None
    dead_lettered_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AutomationExecutionQueuePageRead(APIModel):
    items: list[AutomationExecutionQueueRead]
    total: int
    limit: int
    offset: int
    order_by: str
    order_direction: str


class StoreHealthSummary(APIModel):
    store_id: UUID
    store_name: str
    company_id: UUID
    company_name: str
    store_status: str
    effective_status: str
    runtime_generation: int
    heartbeat_age_seconds: int | None
    last_heartbeat_at: datetime | None
    last_valid_event_at: datetime | None
    active_channels: int
    degraded_channels: int
    failed_webhooks_24h: int
    failed_messages_24h: int
    unresolved_incidents: int
    pending_restarts: int
    queue_depth: int
    active_jobs: int
    backlog_count: int
    version: str
    last_error_at: datetime | None
    last_error_message: str


class StoreHealthDetail(StoreHealthSummary):
    runtime_state: RuntimeStateRead | None
    recent_health_checks: list[StoreHealthCheckRead]
    recent_incidents: list[IncidentRead]
    recent_restarts: list[RestartEventRead]


class StatusOverview(APIModel):
    total_companies: int
    total_stores: int
    online_stores: int
    degraded_stores: int
    offline_stores: int
    restarting_stores: int
    suspended_stores: int
    failed_webhooks_24h: int
    failed_messages_24h: int
    unresolved_incidents: int
    pending_restarts: int
    queued_meta_webhooks: int = 0
    processing_meta_webhooks: int = 0
    retry_scheduled_meta_webhooks: int = 0
    dead_lettered_meta_webhooks: int = 0
    failed_meta_webhooks_total: int = 0
    queued_billing_events: int = 0
    processing_billing_events: int = 0
    retry_scheduled_billing_events: int = 0
    dead_lettered_billing_events: int = 0
    failed_billing_events_total: int = 0
    queued_automation_executions: int = 0
    processing_automation_executions: int = 0
    retry_scheduled_automation_executions: int = 0
    dead_lettered_automation_executions: int = 0
    failed_automation_executions_total: int = 0
    skipped_automation_executions: int = 0
