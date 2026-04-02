from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import IncidentSeverity, RestartEventStatus, RuntimeLifecycleStatus


class StoreRuntimeState(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "store_runtime_states"
    __table_args__ = (UniqueConstraint("store_id"),)

    company_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("client_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    store_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    runtime_generation: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    lifecycle_status: Mapped[RuntimeLifecycleStatus] = mapped_column(
        Enum(RuntimeLifecycleStatus, native_enum=False),
        default=RuntimeLifecycleStatus.OFFLINE,
        nullable=False,
        index=True,
    )
    heartbeat_interval_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    queue_depth: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active_jobs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    backlog_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_worker_shard: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    version: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    last_restart_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_restart_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_restart_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    company = relationship("ClientCompany", lazy="joined")
    store = relationship("Store", lazy="joined")


class StoreHealthCheck(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "store_health_checks"

    company_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("client_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    store_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    runtime_state_id: Mapped[PGUUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("store_runtime_states.id", ondelete="SET NULL"),
        nullable=True,
    )
    lifecycle_status: Mapped[RuntimeLifecycleStatus] = mapped_column(
        Enum(RuntimeLifecycleStatus, native_enum=False),
        nullable=False,
        index=True,
    )
    runtime_generation: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    queue_depth: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active_jobs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    backlog_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cpu_percent: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    memory_percent: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    store = relationship("Store", lazy="joined")
    runtime_state = relationship("StoreRuntimeState", lazy="joined")


class IncidentEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "incident_events"

    company_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("client_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    store_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    severity: Mapped[IncidentSeverity] = mapped_column(
        Enum(IncidentSeverity, native_enum=False),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(80), default="runtime", nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_user_id: Mapped[PGUUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("platform_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    store = relationship("Store", lazy="joined")
    resolved_by_user = relationship("PlatformUser", lazy="joined")


class RestartEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "restart_events"

    company_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("client_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    store_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requested_by_user_id: Mapped[PGUUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("platform_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[RestartEventStatus] = mapped_column(
        Enum(RestartEventStatus, native_enum=False),
        default=RestartEventStatus.REQUESTED,
        nullable=False,
        index=True,
    )
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    before_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    after_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    store = relationship("Store", lazy="joined")
    requested_by_user = relationship("PlatformUser", lazy="joined")
