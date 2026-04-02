from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.automation import AutomationExecution, AutomationRule
from app.models.crm import Conversation
from app.models.enums import AutomationExecutionStatus, AutomationTriggerType


def _coerce_weekdays(value: object) -> list[int]:
    if not isinstance(value, list):
        return [0, 1, 2, 3, 4]
    days: list[int] = []
    for item in value:
        try:
            day = int(item)
        except (TypeError, ValueError):
            continue
        if 0 <= day <= 6:
            days.append(day)
    return days or [0, 1, 2, 3, 4]


def _coerce_local_time(value: object, fallback: time) -> time:
    if isinstance(value, str):
        try:
            parsed = time.fromisoformat(value.strip())
        except ValueError:
            return fallback
        return parsed.replace(second=0, microsecond=0)
    return fallback


def _resolve_business_hours(rule: AutomationRule, conversation: Conversation) -> tuple[ZoneInfo, list[int], time, time]:
    settings = rule.settings_json if isinstance(rule.settings_json, dict) else {}
    business_hours = settings.get("business_hours", {})
    if not isinstance(business_hours, dict):
        business_hours = {}

    timezone_name = business_hours.get("timezone") or conversation.store.timezone or "America/Manaus"
    try:
        zone = ZoneInfo(str(timezone_name))
    except ZoneInfoNotFoundError:
        zone = ZoneInfo("UTC")

    weekdays = _coerce_weekdays(business_hours.get("weekdays"))
    start_time = _coerce_local_time(business_hours.get("start"), time(hour=8, minute=0))
    end_time = _coerce_local_time(business_hours.get("end"), time(hour=18, minute=0))
    return zone, weekdays, start_time, end_time


def is_rule_out_of_hours(
    rule: AutomationRule,
    conversation: Conversation,
    *,
    reference_time: datetime | None = None,
) -> bool:
    zone, weekdays, start_time, end_time = _resolve_business_hours(rule, conversation)
    local_now = (reference_time or datetime.now(timezone.utc)).astimezone(zone)
    if local_now.weekday() not in weekdays:
        return True

    local_clock = local_now.timetz().replace(tzinfo=None)
    if start_time <= end_time:
        return not (start_time <= local_clock < end_time)

    return not (local_clock >= start_time or local_clock < end_time)


async def build_automation_executions_for_trigger(
    session: AsyncSession,
    *,
    trigger_type: AutomationTriggerType,
    conversation: Conversation,
    requested_by_user_id=None,
    metadata: dict | None = None,
    reference_time: datetime | None = None,
) -> list[AutomationExecution]:
    stmt = (
        select(AutomationRule)
        .where(
            AutomationRule.company_id == conversation.company_id,
            AutomationRule.store_id == conversation.store_id,
            AutomationRule.trigger_type == trigger_type,
            AutomationRule.is_active.is_(True),
            or_(AutomationRule.channel_id.is_(None), AutomationRule.channel_id == conversation.channel_id),
        )
        .order_by(AutomationRule.priority.asc(), AutomationRule.created_at.asc())
    )

    rules = (await session.scalars(stmt)).all()
    executions: list[AutomationExecution] = []
    for rule in rules:
        if trigger_type == AutomationTriggerType.OUT_OF_HOURS and not is_rule_out_of_hours(
            rule,
            conversation,
            reference_time=reference_time,
        ):
            continue

        execution_metadata = dict(metadata or {})
        execution_metadata.setdefault("trigger_type", trigger_type.value)
        execution_metadata.setdefault("trigger_origin", "automatic")
        if reference_time:
            execution_metadata.setdefault("trigger_reference_time", reference_time.isoformat())

        execution = AutomationExecution(
            rule_id=rule.id,
            company_id=conversation.company_id,
            store_id=conversation.store_id,
            channel_id=conversation.channel_id,
            conversation_id=conversation.id,
            requested_by_user_id=requested_by_user_id,
            status=AutomationExecutionStatus.QUEUED,
            metadata_json=execution_metadata,
        )
        execution.rule = rule
        execution.conversation = conversation
        session.add(execution)
        executions.append(execution)

    if executions:
        await session.flush()
    return executions
