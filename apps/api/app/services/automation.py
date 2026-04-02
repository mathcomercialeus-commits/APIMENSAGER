from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.automation import AutomationExecution, AutomationRule
from app.models.crm import Conversation, ConversationMessage
from app.models.enums import (
    AutomationActionType,
    AutomationExecutionStatus,
    ConversationEventType,
    ConversationStatus,
    MessageDeliveryStatus,
    MessageDirection,
    MessageSenderType,
    MessageType,
)
from app.models.meta import MessageTemplate
from app.schemas.automation import AutomationExecutionRead, AutomationRuleRead
from app.services.crm import append_conversation_event, conversation_detail_query_options, touch_conversation_after_message
from app.services.meta_whatsapp import (
    MetaAPIConfigurationError,
    WhatsAppCloudAPIClient,
    get_channel_credential,
    is_customer_service_window_open,
    to_whatsapp_recipient,
)


def serialize_automation_rule(rule: AutomationRule) -> AutomationRuleRead:
    return AutomationRuleRead(
        id=rule.id,
        company_id=rule.company_id,
        company_name=rule.company.display_name,
        store_id=rule.store_id,
        store_name=rule.store.name,
        channel_id=rule.channel_id,
        channel_name=rule.channel.name if rule.channel else None,
        name=rule.name,
        description=rule.description,
        trigger_type=rule.trigger_type.value,
        action_type=rule.action_type.value,
        is_active=rule.is_active,
        priority=rule.priority,
        respect_customer_window=rule.respect_customer_window,
        message_body=rule.message_body,
        template_name=rule.template_name,
        template_language_code=rule.template_language_code,
        settings=rule.settings_json,
        last_executed_at=rule.last_executed_at,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


def serialize_automation_execution(execution: AutomationExecution) -> AutomationExecutionRead:
    return AutomationExecutionRead(
        id=execution.id,
        rule_id=execution.rule_id,
        company_id=execution.company_id,
        store_id=execution.store_id,
        channel_id=execution.channel_id,
        conversation_id=execution.conversation_id,
        requested_by_user_id=execution.requested_by_user_id,
        requested_by_user_name=execution.requested_by_user.full_name if execution.requested_by_user else None,
        status=execution.status.value,
        rendered_message=execution.rendered_message,
        result_notes=execution.result_notes,
        provider_message_id=execution.provider_message_id,
        provider_response=execution.provider_response,
        metadata=execution.metadata_json,
        processing_attempts=execution.processing_attempts,
        last_attempt_at=execution.last_attempt_at,
        next_retry_at=execution.next_retry_at,
        dead_lettered_at=execution.dead_lettered_at,
        started_at=execution.started_at,
        finished_at=execution.finished_at,
        created_at=execution.created_at,
        updated_at=execution.updated_at,
    )


async def load_automation_rule(session: AsyncSession, rule_id: UUID) -> AutomationRule | None:
    return await session.get(AutomationRule, rule_id)


async def load_automation_execution(session: AsyncSession, execution_id: UUID) -> AutomationExecution | None:
    return await session.get(AutomationExecution, execution_id)


async def load_conversation_for_automation(session: AsyncSession, conversation_id: UUID) -> Conversation | None:
    return await session.scalar(
        select(Conversation).where(Conversation.id == conversation_id).options(*conversation_detail_query_options())
    )


def render_automation_text(rule: AutomationRule, conversation: Conversation) -> str:
    now = datetime.now(timezone.utc)
    replacements = {
        "[COMPANY]": conversation.company.display_name,
        "[STORE]": conversation.store.name,
        "[CHANNEL]": conversation.channel.name,
        "[CONTACT]": conversation.contact.full_name,
        "[PHONE]": conversation.contact.phone_number_e164,
        "[DATE]": now.strftime("%Y-%m-%d"),
        "[TIME]": now.strftime("%H:%M"),
        "{{company_name}}": conversation.company.display_name,
        "{{store_name}}": conversation.store.name,
        "{{channel_name}}": conversation.channel.name,
        "{{contact_name}}": conversation.contact.full_name,
        "{{contact_phone}}": conversation.contact.phone_number_e164,
    }
    rendered = rule.message_body
    for key, value in replacements.items():
        rendered = rendered.replace(key, value)
    return rendered.strip()


async def _log_automation_message(
    session: AsyncSession,
    *,
    execution: AutomationExecution,
    conversation: Conversation,
    message_type: MessageType,
    body: str,
    provider_message_id: str | None,
    provider_response: dict,
) -> None:
    sent_at = datetime.now(timezone.utc)
    message = ConversationMessage(
        company_id=conversation.company_id,
        store_id=conversation.store_id,
        channel_id=conversation.channel_id,
        conversation_id=conversation.id,
        author_user_id=execution.requested_by_user_id,
        direction=MessageDirection.OUTBOUND,
        sender_type=MessageSenderType.BOT,
        message_type=message_type,
        delivery_status=MessageDeliveryStatus.SENT,
        provider_message_id=provider_message_id,
        text_body=body,
        is_human=False,
        metadata_json={"provider_response": provider_response, "automation_execution_id": str(execution.id)},
        sent_at=sent_at,
    )
    message.conversation = conversation
    message.channel = conversation.channel
    session.add(message)
    await session.flush()
    touch_conversation_after_message(conversation, message)
    await append_conversation_event(
        session,
        conversation=conversation,
        event_type=ConversationEventType.MESSAGE_LOGGED,
        actor_user_id=execution.requested_by_user_id,
        description=f"Automacao '{execution.rule.name}' executada.",
        metadata={"automation_execution_id": str(execution.id), "provider_message_id": provider_message_id},
    )
    execution.provider_message_id = provider_message_id or ""
    execution.provider_response = provider_response


async def execute_automation_execution(session: AsyncSession, execution: AutomationExecution) -> AutomationExecution:
    execution.status = AutomationExecutionStatus.PROCESSING
    execution.started_at = datetime.now(timezone.utc)
    await session.flush()

    rule = execution.rule
    conversation = execution.conversation
    if not rule or not conversation:
        execution.status = AutomationExecutionStatus.FAILED
        execution.result_notes = "Regra ou conversa nao encontrada."
        execution.finished_at = datetime.now(timezone.utc)
        await session.flush()
        return execution

    if not rule.is_active:
        execution.status = AutomationExecutionStatus.SKIPPED
        execution.result_notes = "Regra inativa."
        execution.finished_at = datetime.now(timezone.utc)
        await session.flush()
        return execution

    if conversation.store_id != rule.store_id:
        execution.status = AutomationExecutionStatus.SKIPPED
        execution.result_notes = "Conversa fora do escopo da automacao."
        execution.finished_at = datetime.now(timezone.utc)
        await session.flush()
        return execution

    if rule.channel_id and conversation.channel_id != rule.channel_id:
        execution.status = AutomationExecutionStatus.SKIPPED
        execution.result_notes = "Canal da conversa nao corresponde ao canal da automacao."
        execution.finished_at = datetime.now(timezone.utc)
        await session.flush()
        return execution

    if rule.action_type == AutomationActionType.CLOSE_CONVERSATION:
        conversation.status = ConversationStatus.CLOSED
        conversation.closed_at = datetime.now(timezone.utc)
        conversation.closure_reason = rule.settings_json.get("closure_reason", "automation")
        await append_conversation_event(
            session,
            conversation=conversation,
            event_type=ConversationEventType.STATUS_CHANGED,
            actor_user_id=execution.requested_by_user_id,
            description=f"Automacao '{rule.name}' encerrou a conversa.",
            metadata={"automation_execution_id": str(execution.id)},
        )
        execution.status = AutomationExecutionStatus.EXECUTED
        execution.result_notes = "Conversa encerrada pela automacao."
        execution.finished_at = datetime.now(timezone.utc)
        rule.last_executed_at = execution.finished_at
        await session.flush()
        return execution

    credential = await get_channel_credential(session, conversation.channel_id)
    if not credential or not credential.is_active:
        raise MetaAPIConfigurationError("Credencial Meta inativa para o canal da conversa.")

    client = WhatsAppCloudAPIClient(credential)
    recipient = to_whatsapp_recipient(conversation.contact.phone_number_e164)

    if rule.action_type == AutomationActionType.SEND_TEXT:
        if rule.respect_customer_window and not is_customer_service_window_open(conversation):
            execution.status = AutomationExecutionStatus.SKIPPED
            execution.result_notes = "Janela de atendimento fechada; use template aprovado."
            execution.finished_at = datetime.now(timezone.utc)
            await session.flush()
            return execution
        rendered = render_automation_text(rule, conversation)
        if not rendered:
            execution.status = AutomationExecutionStatus.FAILED
            execution.result_notes = "Mensagem da automacao vazia."
            execution.finished_at = datetime.now(timezone.utc)
            await session.flush()
            return execution
        provider_response = await client.send_text_message(to=recipient, body=rendered, preview_url=False)
        provider_messages = provider_response.get("messages", [])
        provider_message_id = provider_messages[0].get("id") if provider_messages else None
        execution.rendered_message = rendered
        await _log_automation_message(
            session,
            execution=execution,
            conversation=conversation,
            message_type=MessageType.TEXT,
            body=rendered,
            provider_message_id=provider_message_id,
            provider_response=provider_response,
        )
    elif rule.action_type == AutomationActionType.SEND_TEMPLATE:
        if not rule.template_name or not rule.template_language_code:
            execution.status = AutomationExecutionStatus.FAILED
            execution.result_notes = "Template da automacao nao configurado."
            execution.finished_at = datetime.now(timezone.utc)
            await session.flush()
            return execution
        template = await session.scalar(
            select(MessageTemplate).where(
                MessageTemplate.name == rule.template_name,
                MessageTemplate.language_code == rule.template_language_code,
                MessageTemplate.channels.any(id=conversation.channel_id),
            )
        )
        if not template:
            execution.status = AutomationExecutionStatus.FAILED
            execution.result_notes = "Template nao encontrado ou nao vinculado ao canal."
            execution.finished_at = datetime.now(timezone.utc)
            await session.flush()
            return execution
        components = rule.settings_json.get("components", [])
        provider_response = await client.send_template_message(
            to=recipient,
            template_name=rule.template_name,
            language_code=rule.template_language_code,
            components=components,
        )
        provider_messages = provider_response.get("messages", [])
        provider_message_id = provider_messages[0].get("id") if provider_messages else None
        execution.rendered_message = f"[TEMPLATE] {rule.template_name}:{rule.template_language_code}"
        await _log_automation_message(
            session,
            execution=execution,
            conversation=conversation,
            message_type=MessageType.TEMPLATE,
            body=execution.rendered_message,
            provider_message_id=provider_message_id,
            provider_response=provider_response,
        )
    else:
        execution.status = AutomationExecutionStatus.FAILED
        execution.result_notes = "Acao de automacao nao suportada."
        execution.finished_at = datetime.now(timezone.utc)
        await session.flush()
        return execution

    execution.status = AutomationExecutionStatus.EXECUTED
    execution.result_notes = "Automacao executada com sucesso."
    execution.finished_at = datetime.now(timezone.utc)
    rule.last_executed_at = execution.finished_at
    await session.flush()
    return execution
