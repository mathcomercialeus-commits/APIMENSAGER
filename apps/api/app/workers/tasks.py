import asyncio
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.automation import AutomationExecution
from app.models.billing import BillingProviderEvent
from app.models.enums import AutomationExecutionStatus
from app.models.meta import WebhookEvent
from app.services.automation import execute_automation_execution
from app.services.billing import process_asaas_webhook
from app.services.meta_whatsapp import get_channel_credential, process_incoming_webhook_event
from app.workers.celery_app import celery_app


logger = logging.getLogger(__name__)


def _compute_retry_delay(attempt_number: int) -> int:
    base = max(1, settings.queue_retry_backoff_seconds)
    max_delay = max(base, settings.queue_retry_backoff_max_seconds)
    return min(base * (2 ** max(0, attempt_number - 1)), max_delay)


async def _process_meta_webhook_event(event_id: str) -> dict[str, str]:
    async with AsyncSessionLocal() as session:
        event = await session.scalar(select(WebhookEvent).where(WebhookEvent.id == UUID(event_id)))
        if event is None:
            logger.warning("WebhookEvent %s nao encontrado para processamento assincrono.", event_id)
            return {"event_id": event_id, "status": "missing"}

        if event.processing_status in {"processed", "ignored", "dead_lettered"}:
            return {"event_id": event_id, "status": event.processing_status}

        event.processing_attempts += 1
        event.last_attempt_at = datetime.now(timezone.utc)
        event.next_retry_at = None
        event.processing_status = "processing"
        event.processing_notes = "Evento entregue ao worker Celery."
        await session.flush()

        automation_execution_ids: list[str] = []
        try:
            automation_execution_ids = await process_incoming_webhook_event(session, event)
        except Exception as exc:
            credential = None
            if event.channel_id:
                credential = await get_channel_credential(session, event.channel_id)
            if credential:
                credential.last_error_at = datetime.now(timezone.utc)
                credential.status_payload = {**credential.status_payload, "last_error": str(exc)}
            if event.processing_attempts >= settings.queue_max_attempts:
                event.processing_status = "dead_lettered"
                event.processing_notes = str(exc)
                event.dead_lettered_at = datetime.now(timezone.utc)
                event.processed_at = datetime.now(timezone.utc)
                await session.commit()
                logger.exception("Webhook Meta %s enviado para dead-letter.", event_id)
                return {"event_id": event_id, "status": event.processing_status}

            delay = _compute_retry_delay(event.processing_attempts)
            event.processing_status = "retry_scheduled"
            event.processing_notes = f"{exc} | retry agendado em {delay}s."
            event.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
            event.processed_at = None
            await session.commit()
            logger.warning("Webhook Meta %s com retry agendado em %ss.", event_id, delay)
            return {"event_id": event_id, "status": event.processing_status, "action": "retry", "countdown": str(delay)}

        await session.commit()
        for execution_id in automation_execution_ids:
            try:
                enqueue_automation_execution(execution_id)
            except Exception:
                logger.warning("Falha ao enfileirar automacao automatica %s apos webhook %s.", execution_id, event_id)
        return {"event_id": event_id, "status": event.processing_status}


@celery_app.task(name="meta.process_webhook_event", bind=True, max_retries=None)
def process_meta_webhook_event_task(self, event_id: str) -> dict[str, str]:
    result = asyncio.run(_process_meta_webhook_event(event_id))
    if result.get("action") == "retry":
        raise self.retry(countdown=int(result["countdown"]))
    return result


def enqueue_meta_webhook_event(event_id: UUID | str) -> str:
    result = process_meta_webhook_event_task.delay(str(event_id))
    return result.id


async def _process_billing_provider_event(event_id: str) -> dict[str, str]:
    async with AsyncSessionLocal() as session:
        event = await session.scalar(select(BillingProviderEvent).where(BillingProviderEvent.id == UUID(event_id)))
        if event is None:
            logger.warning("BillingProviderEvent %s nao encontrado para processamento assincrono.", event_id)
            return {"event_id": event_id, "status": "missing"}

        if event.processing_status in {"processed", "dead_lettered"}:
            return {"event_id": event_id, "status": event.processing_status}

        event.processing_attempts += 1
        event.last_attempt_at = datetime.now(timezone.utc)
        event.next_retry_at = None
        event.processing_status = "processing"
        event.processing_notes = "Evento entregue ao worker Celery."
        await session.flush()

        try:
            await process_asaas_webhook(session, event.raw_payload, provider_event=event)
        except Exception as exc:
            if event.processing_attempts >= settings.queue_max_attempts:
                event.processing_status = "dead_lettered"
                event.processing_notes = str(exc)
                event.dead_lettered_at = datetime.now(timezone.utc)
                event.processed_at = datetime.now(timezone.utc)
                await session.commit()
                logger.exception("Webhook Billing %s enviado para dead-letter.", event_id)
                return {"event_id": event_id, "status": event.processing_status}

            delay = _compute_retry_delay(event.processing_attempts)
            event.processing_status = "retry_scheduled"
            event.processing_notes = f"{exc} | retry agendado em {delay}s."
            event.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
            event.processed_at = None
            await session.commit()
            logger.warning("Webhook Billing %s com retry agendado em %ss.", event_id, delay)
            return {"event_id": event_id, "status": event.processing_status, "action": "retry", "countdown": str(delay)}

        await session.commit()
        return {"event_id": event_id, "status": event.processing_status}


@celery_app.task(name="billing.process_provider_event", bind=True, max_retries=None)
def process_billing_provider_event_task(self, event_id: str) -> dict[str, str]:
    result = asyncio.run(_process_billing_provider_event(event_id))
    if result.get("action") == "retry":
        raise self.retry(countdown=int(result["countdown"]))
    return result


def enqueue_billing_provider_event(event_id: UUID | str) -> str:
    result = process_billing_provider_event_task.delay(str(event_id))
    return result.id


async def _process_automation_execution(execution_id: str) -> dict[str, str]:
    async with AsyncSessionLocal() as session:
        execution = await session.scalar(select(AutomationExecution).where(AutomationExecution.id == UUID(execution_id)))
        if execution is None:
            logger.warning("AutomationExecution %s nao encontrada para processamento assincrono.", execution_id)
            return {"execution_id": execution_id, "status": "missing"}
        if execution.status.value in {"executed", "skipped"}:
            return {"execution_id": execution_id, "status": execution.status.value}

        execution.processing_attempts += 1
        execution.last_attempt_at = datetime.now(timezone.utc)
        execution.next_retry_at = None
        execution.dead_lettered_at = None
        execution.status = AutomationExecutionStatus.PROCESSING
        execution.result_notes = "Execucao entregue ao worker Celery."
        execution.started_at = datetime.now(timezone.utc)
        execution.finished_at = None
        await session.flush()

        try:
            await execute_automation_execution(session, execution)
            await session.commit()
        except Exception as exc:
            if execution.processing_attempts >= settings.queue_max_attempts:
                execution.status = AutomationExecutionStatus.FAILED
                execution.result_notes = str(exc)
                execution.dead_lettered_at = datetime.now(timezone.utc)
                execution.finished_at = execution.dead_lettered_at
                await session.commit()
                logger.exception("Automacao %s enviada para dead-letter.", execution_id)
                return {"execution_id": execution_id, "status": "dead_lettered"}

            delay = _compute_retry_delay(execution.processing_attempts)
            execution.status = AutomationExecutionStatus.FAILED
            execution.result_notes = f"{exc} | retry agendado em {delay}s."
            execution.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
            execution.finished_at = datetime.now(timezone.utc)
            await session.commit()
            logger.warning("Automacao %s com retry agendado em %ss.", execution_id, delay)
            return {"execution_id": execution_id, "status": "retry_scheduled", "action": "retry", "countdown": str(delay)}
        return {"execution_id": execution_id, "status": execution.status.value}


@celery_app.task(name="automations.execute_rule", bind=True, max_retries=None)
def process_automation_execution_task(self, execution_id: str) -> dict[str, str]:
    result = asyncio.run(_process_automation_execution(execution_id))
    if result.get("action") == "retry":
        raise self.retry(countdown=int(result["countdown"]))
    return result


def enqueue_automation_execution(execution_id: UUID | str) -> str:
    result = process_automation_execution_task.delay(str(execution_id))
    return result.id
