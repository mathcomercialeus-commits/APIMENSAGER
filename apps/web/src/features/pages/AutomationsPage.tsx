"use client";

import { useEffect, useMemo, useState } from "react";

import { EmptyState } from "@/src/components/EmptyState";
import { JsonBox } from "@/src/components/JsonBox";
import { PageHeader } from "@/src/components/PageHeader";
import { SectionCard } from "@/src/components/SectionCard";
import { StatusBadge } from "@/src/components/StatusBadge";
import { buildQuery } from "@/src/lib/api";
import { formatDateTime, formatStatus, truncate } from "@/src/lib/format";
import { resolveScopedCompanyId, resolveScopedStoreId } from "@/src/lib/scope";
import { useAuth } from "@/src/providers/AuthProvider";
import { useWorkspace } from "@/src/providers/WorkspaceProvider";
import type {
  AutomationExecutionRead,
  AutomationRuleRead,
  ConversationSummaryRead,
  MessageTemplateRead,
  UUID,
  WhatsAppChannelRead
} from "@/src/types/api";

type RuleDraft = {
  name: string;
  description: string;
  trigger_type: string;
  action_type: string;
  is_active: boolean;
  priority: number;
  respect_customer_window: boolean;
  channel_id: string;
  message_body: string;
  template_name: string;
  template_language_code: string;
  settings: string;
};

const DEFAULT_MESSAGE_BODY = "Oi [CONTACT], aqui e [STORE]. Como posso ajudar?";

function createEmptyDraft(): RuleDraft {
  return {
    name: "",
    description: "",
    trigger_type: "manual",
    action_type: "send_text",
    is_active: true,
    priority: 100,
    respect_customer_window: true,
    channel_id: "",
    message_body: DEFAULT_MESSAGE_BODY,
    template_name: "",
    template_language_code: "",
    settings: "{}"
  };
}

function mapRuleToDraft(rule: AutomationRuleRead): RuleDraft {
  return {
    name: rule.name,
    description: rule.description,
    trigger_type: rule.trigger_type,
    action_type: rule.action_type,
    is_active: rule.is_active,
    priority: rule.priority,
    respect_customer_window: rule.respect_customer_window,
    channel_id: rule.channel_id || "",
    message_body: rule.message_body,
    template_name: rule.template_name,
    template_language_code: rule.template_language_code,
    settings: JSON.stringify(rule.settings || {}, null, 2)
  };
}

function parseJsonField(raw: string, fallbackLabel: string): Record<string, unknown> {
  const text = raw.trim();
  if (!text) {
    return {};
  }
  try {
    const parsed = JSON.parse(text) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error(`${fallbackLabel} precisa ser um objeto JSON.`);
    }
    return parsed as Record<string, unknown>;
  } catch (error) {
    if (error instanceof Error) {
      throw error;
    }
    throw new Error(`JSON invalido em ${fallbackLabel}.`);
  }
}

export function AutomationsPage() {
  const { apiFetch } = useAuth();
  const { companies, stores, selectedCompanyId, selectedStoreId } = useWorkspace();
  const [rules, setRules] = useState<AutomationRuleRead[]>([]);
  const [selectedRuleId, setSelectedRuleId] = useState<UUID | "">("");
  const [draft, setDraft] = useState<RuleDraft>(() => createEmptyDraft());
  const [executions, setExecutions] = useState<AutomationExecutionRead[]>([]);
  const [channels, setChannels] = useState<WhatsAppChannelRead[]>([]);
  const [conversations, setConversations] = useState<ConversationSummaryRead[]>([]);
  const [templates, setTemplates] = useState<MessageTemplateRead[]>([]);
  const [selectedConversationId, setSelectedConversationId] = useState("");
  const [executionMetadata, setExecutionMetadata] = useState("{\n  \"origin\": \"web_panel\"\n}");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const companyId = resolveScopedCompanyId(selectedCompanyId, selectedStoreId, stores, companies);
  const storeId = resolveScopedStoreId(selectedStoreId);
  const selectedRule = useMemo(
    () => rules.find((rule) => rule.id === selectedRuleId) || null,
    [rules, selectedRuleId]
  );
  const isEditing = Boolean(selectedRule);

  async function loadRules(preferredRuleId?: string | null) {
    if (!companyId) {
      setRules([]);
      setSelectedRuleId("");
      return;
    }

    const response = await apiFetch<AutomationRuleRead[]>(
      `/automations/rules${buildQuery({ company_id: companyId, store_id: storeId })}`
    );
    setRules(response);
    setSelectedRuleId((current) => {
      const candidate = preferredRuleId || current;
      if (candidate && response.some((rule) => rule.id === candidate)) {
        return candidate;
      }
      return response[0]?.id || "";
    });
  }

  async function loadRuleExecutions(ruleId: string) {
    const response = await apiFetch<AutomationExecutionRead[]>(`/automations/rules/${ruleId}/executions`);
    setExecutions(response);
  }

  async function loadRuntimeAssets(targetStoreId: string | null) {
    if (!targetStoreId) {
      setChannels([]);
      setConversations([]);
      setSelectedConversationId("");
      return;
    }

    const [channelsResponse, conversationsResponse] = await Promise.all([
      apiFetch<WhatsAppChannelRead[]>(`/channels${buildQuery({ store_id: targetStoreId })}`),
      apiFetch<ConversationSummaryRead[]>(`/crm/conversations${buildQuery({ store_id: targetStoreId })}`)
    ]);
    setChannels(channelsResponse);
    setConversations(conversationsResponse);
    setSelectedConversationId((current) => {
      if (current && conversationsResponse.some((conversation) => conversation.id === current)) {
        return current;
      }
      return conversationsResponse[0]?.id || "";
    });
  }

  async function loadTemplates(channelId: string | null) {
    if (!channelId) {
      setTemplates([]);
      return;
    }
    const response = await apiFetch<MessageTemplateRead[]>(`/meta/channels/${channelId}/templates`);
    setTemplates(response);
  }

  useEffect(() => {
    async function load() {
      setError(null);
      try {
        await loadRules();
      } catch (exception) {
        setError(exception instanceof Error ? exception.message : "Falha ao carregar automacoes.");
      }
    }
    void load();
  }, [apiFetch, companyId, storeId]);

  useEffect(() => {
    async function syncSelection() {
      setError(null);
      try {
        if (selectedRule) {
          setDraft(mapRuleToDraft(selectedRule));
          await Promise.all([
            loadRuleExecutions(selectedRule.id),
            loadRuntimeAssets(selectedRule.store_id),
            loadTemplates(selectedRule.channel_id)
          ]);
          return;
        }

        setDraft(createEmptyDraft());
        setExecutions([]);
        setTemplates([]);
        await loadRuntimeAssets(storeId);
      } catch (exception) {
        setError(exception instanceof Error ? exception.message : "Falha ao carregar o contexto da automacao.");
      }
    }

    void syncSelection();
  }, [apiFetch, selectedRule, storeId]);

  function resetEditor() {
    setSelectedRuleId("");
    setDraft(createEmptyDraft());
    setExecutions([]);
    setTemplates([]);
    setMessage(null);
    setError(null);
  }

  async function saveRule(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    setError(null);

    try {
      const settings = parseJsonField(draft.settings, "settings");
      const payload = {
        channel_id: draft.channel_id || null,
        name: draft.name.trim(),
        description: draft.description.trim(),
        trigger_type: draft.trigger_type,
        action_type: draft.action_type,
        is_active: draft.is_active,
        priority: draft.priority,
        respect_customer_window: draft.respect_customer_window,
        message_body: draft.message_body,
        template_name: draft.template_name.trim(),
        template_language_code: draft.template_language_code.trim(),
        settings
      };

      if (selectedRule) {
        const updated = await apiFetch<AutomationRuleRead>(`/automations/rules/${selectedRule.id}`, {
          method: "PATCH",
          body: payload
        });
        setMessage("Automacao atualizada.");
        await loadRules(updated.id);
        return;
      }

      if (!storeId) {
        throw new Error("Selecione uma loja para criar automacoes.");
      }

      const created = await apiFetch<AutomationRuleRead>("/automations/rules", {
        method: "POST",
        body: { ...payload, store_id: storeId }
      });
      setMessage("Automacao criada.");
      await loadRules(created.id);
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Falha ao salvar automacao.");
    }
  }

  async function executeRule() {
    if (!selectedRule) {
      return;
    }

    setMessage(null);
    setError(null);

    try {
      if (!selectedConversationId) {
        throw new Error("Selecione uma conversa para executar a automacao.");
      }
      const metadata = parseJsonField(executionMetadata, "metadata da execucao");
      await apiFetch<AutomationExecutionRead>(`/automations/rules/${selectedRule.id}/execute`, {
        method: "POST",
        body: { conversation_id: selectedConversationId, metadata }
      });
      setMessage("Execucao enfileirada.");
      await Promise.all([loadRuleExecutions(selectedRule.id), loadRules(selectedRule.id)]);
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Falha ao executar automacao.");
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        title="Automacoes oficiais"
        description="Regras por loja e canal, executadas pela fila oficial e respeitando os limites da Meta."
      />

      {message ? <div className="callout callout--success">{message}</div> : null}
      {error ? <div className="callout callout--danger">{error}</div> : null}
      {!storeId ? (
        <div className="callout callout--info">
          Selecione uma loja no topo do portal para criar novas automacoes. Sem loja fixa, a tela entra em modo de
          consulta por empresa.
        </div>
      ) : null}
      {selectedRule && storeId && selectedRule.store_id !== storeId ? (
        <div className="callout callout--info">
          A regra selecionada pertence a outra loja do mesmo cliente. A execucao manual e a lista de conversas foram
          ajustadas automaticamente para o escopo correto.
        </div>
      ) : null}

      <div className="two-column-grid">
        <SectionCard title="Regras do escopo" description="Selecione uma regra existente ou abra um rascunho novo.">
          <div className="page-stack">
            <div className="toolbar">
              <button type="button" className="button button--secondary" onClick={resetEditor}>
                Nova automacao
              </button>
            </div>

            {rules.length ? (
              <div className="timeline-list">
                {rules.map((rule) => (
                  <button
                    key={rule.id}
                    type="button"
                    className={selectedRule?.id === rule.id ? "mini-panel is-active is-selectable" : "mini-panel is-selectable"}
                    onClick={() => setSelectedRuleId(rule.id)}
                  >
                    <div className="mini-panel__header">
                      <strong>{rule.name}</strong>
                      <StatusBadge status={rule.is_active ? "active" : "inactive"} />
                    </div>
                    <p>{truncate(rule.description || `${rule.store_name}${rule.channel_name ? ` / ${rule.channel_name}` : ""}`, 96)}</p>
                    <div className="tag-row">
                      <span className="pill">{rule.store_name}</span>
                      {rule.channel_name ? <span className="pill">{rule.channel_name}</span> : null}
                      <span className="pill">{formatStatus(rule.trigger_type)}</span>
                      <span className="pill">{formatStatus(rule.action_type)}</span>
                      <span className="pill">P{rule.priority}</span>
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <EmptyState
                title="Sem automacoes cadastradas"
                description="Crie a primeira regra para a empresa ou loja em foco."
              />
            )}
          </div>
        </SectionCard>

        <SectionCard
          title={isEditing ? "Editar automacao" : "Nova automacao"}
          description="Texto, template e encerramento de conversa dentro do fluxo oficial da plataforma."
        >
          {isEditing || storeId ? (
            <form className="form-grid form-grid--two" onSubmit={saveRule}>
              <label>
                <span>Nome</span>
                <input
                  value={draft.name}
                  onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))}
                  required
                />
              </label>
              <label>
                <span>Prioridade</span>
                <input
                  type="number"
                  min={1}
                  max={1000}
                  value={draft.priority}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, priority: Number(event.target.value || 100) }))
                  }
                />
              </label>

              <label>
                <span>Trigger</span>
                <select
                  value={draft.trigger_type}
                  onChange={(event) => setDraft((current) => ({ ...current, trigger_type: event.target.value }))}
                >
                  <option value="manual">Manual</option>
                  <option value="conversation_opened">Conversa aberta</option>
                  <option value="conversation_assigned">Conversa atribuida</option>
                  <option value="out_of_hours">Fora do horario</option>
                </select>
              </label>
              <label>
                <span>Acao</span>
                <select
                  value={draft.action_type}
                  onChange={(event) => setDraft((current) => ({ ...current, action_type: event.target.value }))}
                >
                  <option value="send_text">Enviar texto</option>
                  <option value="send_template">Enviar template</option>
                  <option value="close_conversation">Encerrar conversa</option>
                </select>
              </label>

              <label className="form-grid__span-2">
                <span>Canal opcional</span>
                <select
                  value={draft.channel_id}
                  onChange={(event) => setDraft((current) => ({ ...current, channel_id: event.target.value }))}
                >
                  <option value="">Todos os canais da loja</option>
                  {channels.map((channel) => (
                    <option key={channel.id} value={channel.id}>
                      {channel.name}
                    </option>
                  ))}
                </select>
              </label>

              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={draft.is_active}
                  onChange={(event) => setDraft((current) => ({ ...current, is_active: event.target.checked }))}
                />
                <span>Regra ativa</span>
              </label>
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={draft.respect_customer_window}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, respect_customer_window: event.target.checked }))
                  }
                />
                <span>Respeitar janela de 24h</span>
              </label>

              <label className="form-grid__span-2">
                <span>Descricao</span>
                <textarea
                  value={draft.description}
                  onChange={(event) => setDraft((current) => ({ ...current, description: event.target.value }))}
                />
              </label>

              {draft.action_type === "send_text" ? (
                <label className="form-grid__span-2">
                  <span>Mensagem</span>
                  <textarea
                    value={draft.message_body}
                    onChange={(event) => setDraft((current) => ({ ...current, message_body: event.target.value }))}
                  />
                </label>
              ) : null}

              {draft.action_type === "send_template" ? (
                <>
                  <label>
                    <span>Template</span>
                    <input
                      value={draft.template_name}
                      onChange={(event) => setDraft((current) => ({ ...current, template_name: event.target.value }))}
                    />
                  </label>
                  <label>
                    <span>Idioma do template</span>
                    <input
                      value={draft.template_language_code}
                      onChange={(event) =>
                        setDraft((current) => ({ ...current, template_language_code: event.target.value }))
                      }
                    />
                  </label>
                </>
              ) : null}

              {draft.action_type === "close_conversation" ? (
                <div className="form-grid__span-2 callout callout--info">
                  Use <code>{`{"closure_reason":"automation"}`}</code> no JSON abaixo para controlar o motivo de
                  encerramento.
                </div>
              ) : null}

              <label className="form-grid__span-2">
                <span>Settings JSON</span>
                <textarea
                  value={draft.settings}
                  onChange={(event) => setDraft((current) => ({ ...current, settings: event.target.value }))}
                />
              </label>

              <div className="form-grid__span-2 toolbar">
                <button type="submit" className="button button--primary">
                  {isEditing ? "Salvar automacao" : "Criar automacao"}
                </button>
                {isEditing ? (
                  <button type="button" className="button button--secondary" onClick={resetEditor}>
                    Duplicar em novo rascunho
                  </button>
                ) : null}
              </div>

              {selectedRule ? (
                <div className="form-grid__span-2 data-pairs">
                  <div>
                    <dt>Empresa</dt>
                    <dd>{selectedRule.company_name}</dd>
                  </div>
                  <div>
                    <dt>Loja</dt>
                    <dd>{selectedRule.store_name}</dd>
                  </div>
                  <div>
                    <dt>Canal atual</dt>
                    <dd>{selectedRule.channel_name || "Todos os canais da loja"}</dd>
                  </div>
                  <div>
                    <dt>Ultima execucao</dt>
                    <dd>{formatDateTime(selectedRule.last_executed_at)}</dd>
                  </div>
                </div>
              ) : null}
            </form>
          ) : (
            <EmptyState
              title="Selecione uma loja"
              description="A criacao de automacoes exige escopo de loja, mesmo na visao consolidada da empresa."
            />
          )}
        </SectionCard>
      </div>

      <div className="two-column-grid">
        <SectionCard title="Execucao controlada" description="Teste manual em uma conversa valida do mesmo escopo.">
          {selectedRule ? (
            <div className="page-stack">
              <label>
                <span>Conversa</span>
                <select value={selectedConversationId} onChange={(event) => setSelectedConversationId(event.target.value)}>
                  <option value="">Selecione uma conversa</option>
                  {conversations.map((conversation) => (
                    <option key={conversation.id} value={conversation.id}>
                      {conversation.contact_name} / {conversation.channel.name} / {conversation.status}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                <span>Metadata JSON</span>
                <textarea value={executionMetadata} onChange={(event) => setExecutionMetadata(event.target.value)} />
              </label>

              <button type="button" className="button button--secondary" onClick={() => void executeRule()}>
                Executar automacao
              </button>

              {templates.length ? <JsonBox title="Templates vinculados ao canal" value={templates} /> : null}
            </div>
          ) : (
            <EmptyState
              title="Selecione uma regra"
              description="A execucao manual fica disponivel quando uma automacao existente esta em foco."
            />
          )}
        </SectionCard>

        <SectionCard title="Historico de execucoes" description="Status da fila, retorno da Meta e resultado persistido.">
          {selectedRule ? (
            executions.length ? (
              <div className="timeline-list">
                {executions.map((execution) => (
                  <article key={execution.id} className="mini-panel">
                    <div className="mini-panel__header">
                      <strong>{execution.requested_by_user_name || "Sistema"}</strong>
                      <StatusBadge status={execution.status} />
                    </div>
                    <p>{execution.result_notes || execution.rendered_message || "Sem detalhes retornados."}</p>
                    <div className="tag-row">
                      <span className="pill">Attempts {execution.processing_attempts}</span>
                      <span className="pill">Inicio: {formatDateTime(execution.started_at)}</span>
                      <span className="pill">Fim: {formatDateTime(execution.finished_at)}</span>
                      <span className="pill">Proxima: {formatDateTime(execution.next_retry_at)}</span>
                      {execution.dead_lettered_at ? (
                        <span className="pill">Dead-letter: {formatDateTime(execution.dead_lettered_at)}</span>
                      ) : null}
                      {execution.provider_message_id ? (
                        <span className="pill">Provider: {truncate(execution.provider_message_id, 18)}</span>
                      ) : null}
                    </div>
                    {Object.keys(execution.provider_response || {}).length ? (
                      <JsonBox title="Provider response" value={execution.provider_response} />
                    ) : null}
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState
                title="Sem execucoes ainda"
                description="As execucoes manuais e automatizadas desta regra aparecerao aqui."
              />
            )
          ) : (
            <EmptyState
              title="Nenhuma regra selecionada"
              description="Escolha uma automacao para acompanhar seu historico."
            />
          )}
        </SectionCard>
      </div>
    </div>
  );
}
