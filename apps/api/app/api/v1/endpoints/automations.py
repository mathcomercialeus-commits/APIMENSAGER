from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor, request_ip
from app.core.database import get_db_session
from app.models.automation import AutomationExecution, AutomationRule
from app.models.crm import WhatsAppChannel
from app.models.enums import AutomationActionType, AutomationExecutionStatus, AutomationTriggerType
from app.schemas.automation import AutomationExecuteRequest, AutomationExecutionRead, AutomationRuleCreate, AutomationRuleRead, AutomationRuleUpdate
from app.services.access import CurrentActor, get_store_or_404
from app.services.audit import record_audit_log
from app.services.automation import (
    execute_automation_execution,
    load_automation_rule,
    load_conversation_for_automation,
    serialize_automation_execution,
    serialize_automation_rule,
)
from app.workers.tasks import enqueue_automation_execution


router = APIRouter()


def _ensure_automation_permission(actor: CurrentActor, *, company_id: UUID, store_id: UUID, manage: bool = False) -> None:
    permission = "automations.manage" if manage else "automations.view"
    if not actor.has_permission(permission, company_id=company_id, store_id=store_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para automacoes neste escopo.")


@router.get("/rules", response_model=list[AutomationRuleRead])
async def list_automation_rules(
    company_id: UUID | None = Query(default=None),
    store_id: UUID | None = Query(default=None),
    channel_id: UUID | None = Query(default=None),
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> list[AutomationRuleRead]:
    stmt = select(AutomationRule).order_by(AutomationRule.priority.asc(), AutomationRule.name.asc())
    if store_id:
        store = await get_store_or_404(session, store_id)
        if not store:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loja nao encontrada.")
        _ensure_automation_permission(actor, company_id=store.company_id, store_id=store.id, manage=False)
        stmt = stmt.where(AutomationRule.store_id == store.id)
    elif company_id:
        if not actor.can_access_company(company_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem acesso a esta empresa.")
        stmt = stmt.where(AutomationRule.company_id == company_id)
    elif not actor.is_superadmin:
        store_ids = list(actor.store_roles.keys())
        company_ids = list(actor.company_roles.keys())
        if store_ids:
            stmt = stmt.where(AutomationRule.store_id.in_(store_ids))
        elif company_ids:
            stmt = stmt.where(AutomationRule.company_id.in_(company_ids))
        else:
            return []

    if channel_id:
        stmt = stmt.where(AutomationRule.channel_id == channel_id)

    rules = (await session.scalars(stmt)).all()
    return [serialize_automation_rule(item) for item in rules]


@router.post("/rules", response_model=AutomationRuleRead, status_code=status.HTTP_201_CREATED)
async def create_automation_rule(
    payload: AutomationRuleCreate,
    request: Request,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> AutomationRuleRead:
    store = await get_store_or_404(session, payload.store_id)
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loja nao encontrada.")
    _ensure_automation_permission(actor, company_id=store.company_id, store_id=store.id, manage=True)

    channel = None
    if payload.channel_id:
        channel = await session.get(WhatsAppChannel, payload.channel_id)
        if not channel or channel.store_id != store.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Canal invalido para esta automacao.")

    try:
        trigger_type = AutomationTriggerType(payload.trigger_type)
        action_type = AutomationActionType(payload.action_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo de automacao invalido.") from exc

    rule = AutomationRule(
        company_id=store.company_id,
        store_id=store.id,
        channel_id=channel.id if channel else None,
        name=payload.name.strip(),
        description=payload.description.strip(),
        trigger_type=trigger_type,
        action_type=action_type,
        is_active=payload.is_active,
        priority=payload.priority,
        respect_customer_window=payload.respect_customer_window,
        message_body=payload.message_body.strip(),
        template_name=payload.template_name.strip(),
        template_language_code=payload.template_language_code.strip(),
        settings_json=payload.settings,
    )
    session.add(rule)
    await session.flush()
    await record_audit_log(
        session,
        action="automations.rule_created",
        resource_type="automation_rule",
        actor_user_id=actor.user.id,
        resource_id=str(rule.id),
        company_id=rule.company_id,
        store_id=rule.store_id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"trigger_type": rule.trigger_type.value, "action_type": rule.action_type.value},
    )
    await session.commit()
    await session.refresh(rule)
    return serialize_automation_rule(rule)


@router.patch("/rules/{rule_id}", response_model=AutomationRuleRead)
async def update_automation_rule(
    rule_id: UUID,
    payload: AutomationRuleUpdate,
    request: Request,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> AutomationRuleRead:
    rule = await load_automation_rule(session, rule_id)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automacao nao encontrada.")
    _ensure_automation_permission(actor, company_id=rule.company_id, store_id=rule.store_id, manage=True)

    if payload.channel_id is not None:
        if payload.channel_id:
            channel = await session.get(WhatsAppChannel, payload.channel_id)
            if not channel or channel.store_id != rule.store_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Canal invalido para esta automacao.")
            rule.channel_id = channel.id
        else:
            rule.channel_id = None
    if payload.name is not None:
        rule.name = payload.name.strip()
    if payload.description is not None:
        rule.description = payload.description.strip()
    if payload.trigger_type is not None:
        try:
            rule.trigger_type = AutomationTriggerType(payload.trigger_type)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Trigger invalido.") from exc
    if payload.action_type is not None:
        try:
            rule.action_type = AutomationActionType(payload.action_type)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Acao invalida.") from exc
    if payload.is_active is not None:
        rule.is_active = payload.is_active
    if payload.priority is not None:
        rule.priority = payload.priority
    if payload.respect_customer_window is not None:
        rule.respect_customer_window = payload.respect_customer_window
    if payload.message_body is not None:
        rule.message_body = payload.message_body.strip()
    if payload.template_name is not None:
        rule.template_name = payload.template_name.strip()
    if payload.template_language_code is not None:
        rule.template_language_code = payload.template_language_code.strip()
    if payload.settings is not None:
        rule.settings_json = payload.settings

    await record_audit_log(
        session,
        action="automations.rule_updated",
        resource_type="automation_rule",
        actor_user_id=actor.user.id,
        resource_id=str(rule.id),
        company_id=rule.company_id,
        store_id=rule.store_id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
    )
    await session.commit()
    await session.refresh(rule)
    return serialize_automation_rule(rule)


@router.get("/rules/{rule_id}/executions", response_model=list[AutomationExecutionRead])
async def list_automation_executions(
    rule_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> list[AutomationExecutionRead]:
    rule = await load_automation_rule(session, rule_id)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automacao nao encontrada.")
    _ensure_automation_permission(actor, company_id=rule.company_id, store_id=rule.store_id, manage=False)
    executions = (await session.scalars(select(AutomationExecution).where(AutomationExecution.rule_id == rule.id).order_by(AutomationExecution.created_at.desc()).limit(limit))).all()
    return [serialize_automation_execution(item) for item in executions]


@router.post("/rules/{rule_id}/execute", response_model=AutomationExecutionRead, status_code=status.HTTP_202_ACCEPTED)
async def execute_automation_rule(
    rule_id: UUID,
    payload: AutomationExecuteRequest,
    request: Request,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> AutomationExecutionRead:
    rule = await load_automation_rule(session, rule_id)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automacao nao encontrada.")
    _ensure_automation_permission(actor, company_id=rule.company_id, store_id=rule.store_id, manage=True)

    conversation = await load_conversation_for_automation(session, payload.conversation_id)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa nao encontrada.")
    if conversation.company_id != rule.company_id or conversation.store_id != rule.store_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Conversa fora do escopo da automacao.")

    execution = AutomationExecution(
        rule_id=rule.id,
        company_id=rule.company_id,
        store_id=rule.store_id,
        channel_id=conversation.channel_id,
        conversation_id=conversation.id,
        requested_by_user_id=actor.user.id,
        status=AutomationExecutionStatus.QUEUED,
        metadata_json=payload.metadata,
    )
    execution.rule = rule
    execution.conversation = conversation
    session.add(execution)
    await session.flush()
    await record_audit_log(
        session,
        action="automations.execution_requested",
        resource_type="automation_execution",
        actor_user_id=actor.user.id,
        resource_id=str(execution.id),
        company_id=rule.company_id,
        store_id=rule.store_id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"rule_id": str(rule.id), "conversation_id": str(conversation.id)},
    )
    await session.commit()

    try:
        enqueue_automation_execution(execution.id)
    except Exception:
        execution = await session.get(AutomationExecution, execution.id)
        if execution:
            execution.rule = rule
            execution.conversation = conversation
            await execute_automation_execution(session, execution)
            await session.commit()
            await session.refresh(execution)
            return serialize_automation_execution(execution)
        raise

    execution = await session.get(AutomationExecution, execution.id)
    return serialize_automation_execution(execution)
