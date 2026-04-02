"use client";

import { useEffect, useMemo, useState } from "react";

import { EmptyState } from "@/src/components/EmptyState";
import { JsonBox } from "@/src/components/JsonBox";
import { PageHeader } from "@/src/components/PageHeader";
import { SectionCard } from "@/src/components/SectionCard";
import { StatCard } from "@/src/components/StatCard";
import { StatusBadge } from "@/src/components/StatusBadge";
import { buildQuery } from "@/src/lib/api";
import { formatDateTime } from "@/src/lib/format";
import { isSuperadmin, resolveScopedCompanyId } from "@/src/lib/scope";
import { useAuth } from "@/src/providers/AuthProvider";
import { useWorkspace } from "@/src/providers/WorkspaceProvider";
import type {
  AutomationExecutionQueuePageRead,
  AutomationExecutionQueueRead,
  AutomationRuleRead,
  BillingProviderEventPageRead,
  BillingProviderEventRead,
  MetaWebhookQueuePageRead,
  MetaWebhookQueueEventRead,
  StatusOverview,
  StoreHealthDetail,
  StoreHealthSummary,
  WhatsAppChannelRead
} from "@/src/types/api";

const AUTOMATION_CRITICAL_STATUS_DEFAULT = "processing,retry_scheduled,dead_lettered,skipped";
const AUTOMATION_PAGE_LIMIT_DEFAULT = 20;
const AUTOMATION_STATUS_OPTIONS = [
  { label: "Criticas", value: AUTOMATION_CRITICAL_STATUS_DEFAULT },
  { label: "Em processamento", value: "processing" },
  { label: "Retry agendado", value: "retry_scheduled" },
  { label: "Dead-letter", value: "dead_lettered" },
  { label: "Ignoradas", value: "skipped" },
  { label: "Falhas sem retry", value: "failed" },
  { label: "Executadas", value: "executed" },
  { label: "Todas", value: "queued,processing,retry_scheduled,dead_lettered,failed,executed,skipped" }
] as const;
const AUTOMATION_ORDER_OPTIONS = [
  { label: "Criacao", value: "created_at" },
  { label: "Atualizacao", value: "updated_at" },
  { label: "Inicio do processamento", value: "started_at" },
  { label: "Proxima retentativa", value: "next_retry_at" },
  { label: "Tentativas", value: "processing_attempts" }
] as const;
const QUEUE_PAGE_LIMIT_DEFAULT = 10;
const RETRY_QUEUE_ORDER_OPTIONS = [
  { label: "Atualizacao", value: "updated_at" },
  { label: "Criacao", value: "created_at" },
  { label: "Proxima retentativa", value: "next_retry_at" },
  { label: "Processado em", value: "processed_at" },
  { label: "Tentativas", value: "processing_attempts" }
] as const;

function toStartOfDayIso(value: string): string | undefined {
  if (!value) {
    return undefined;
  }
  return new Date(`${value}T00:00:00`).toISOString();
}

function toEndOfDayIso(value: string): string | undefined {
  if (!value) {
    return undefined;
  }
  return new Date(`${value}T23:59:59.999`).toISOString();
}

function downloadCsv(filenamePrefix: string, headers: string[], rows: string[][]): void {
  if (typeof window === "undefined") {
    return;
  }

  const escapeCsv = (value: string) => `"${value.replace(/"/g, "\"\"")}"`;
  const csv = [headers.join(","), ...rows.map((row) => row.map((item) => escapeCsv(item)).join(","))].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = window.URL.createObjectURL(blob);
  const link = window.document.createElement("a");
  const today = new Date().toISOString().slice(0, 10);
  link.href = url;
  link.download = `${filenamePrefix}-${today}.csv`;
  window.document.body.appendChild(link);
  link.click();
  window.document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

export function OpsPage() {
  const { apiFetch, user } = useAuth();
  const { companies, stores, selectedCompanyId, selectedStoreId } = useWorkspace();
  const [overview, setOverview] = useState<StatusOverview | null>(null);
  const [health, setHealth] = useState<StoreHealthSummary[]>([]);
  const [detail, setDetail] = useState<StoreHealthDetail | null>(null);
  const [metaQueue, setMetaQueue] = useState<MetaWebhookQueueEventRead[]>([]);
  const [billingQueue, setBillingQueue] = useState<BillingProviderEventRead[]>([]);
  const [metaQueueTotal, setMetaQueueTotal] = useState(0);
  const [billingQueueTotal, setBillingQueueTotal] = useState(0);
  const [metaQueueOffset, setMetaQueueOffset] = useState(0);
  const [billingQueueOffset, setBillingQueueOffset] = useState(0);
  const [metaQueueOrderBy, setMetaQueueOrderBy] = useState("updated_at");
  const [billingQueueOrderBy, setBillingQueueOrderBy] = useState("updated_at");
  const [metaQueueOrderDirection, setMetaQueueOrderDirection] = useState("desc");
  const [billingQueueOrderDirection, setBillingQueueOrderDirection] = useState("desc");
  const [automationQueue, setAutomationQueue] = useState<AutomationExecutionQueueRead[]>([]);
  const [automationRules, setAutomationRules] = useState<AutomationRuleRead[]>([]);
  const [automationChannels, setAutomationChannels] = useState<WhatsAppChannelRead[]>([]);
  const [selectedAutomationRuleId, setSelectedAutomationRuleId] = useState("");
  const [selectedAutomationChannelId, setSelectedAutomationChannelId] = useState("");
  const [selectedAutomationStatus, setSelectedAutomationStatus] = useState(AUTOMATION_CRITICAL_STATUS_DEFAULT);
  const [automationOrderBy, setAutomationOrderBy] = useState("created_at");
  const [automationOrderDirection, setAutomationOrderDirection] = useState("desc");
  const [automationPageOffset, setAutomationPageOffset] = useState(0);
  const [automationPageLimit, setAutomationPageLimit] = useState(AUTOMATION_PAGE_LIMIT_DEFAULT);
  const [automationQueueTotal, setAutomationQueueTotal] = useState(0);
  const [automationCreatedFrom, setAutomationCreatedFrom] = useState("");
  const [automationCreatedTo, setAutomationCreatedTo] = useState("");
  const [restartReason, setRestartReason] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const companyId = resolveScopedCompanyId(selectedCompanyId, selectedStoreId, stores, companies);
  const canRestart = Boolean(user && isSuperadmin(user));
  const filteredAutomationRules = useMemo(() => {
    if (!selectedAutomationChannelId) {
      return automationRules;
    }
    return automationRules.filter(
      (rule) => !rule.channel_id || rule.channel_id === selectedAutomationChannelId
    );
  }, [automationRules, selectedAutomationChannelId]);
  const metaCurrentPage = Math.floor(metaQueueOffset / QUEUE_PAGE_LIMIT_DEFAULT) + 1;
  const metaTotalPages = Math.max(1, Math.ceil(metaQueueTotal / QUEUE_PAGE_LIMIT_DEFAULT));
  const billingCurrentPage = Math.floor(billingQueueOffset / QUEUE_PAGE_LIMIT_DEFAULT) + 1;
  const billingTotalPages = Math.max(1, Math.ceil(billingQueueTotal / QUEUE_PAGE_LIMIT_DEFAULT));
  const automationCurrentPage = Math.floor(automationPageOffset / automationPageLimit) + 1;
  const automationTotalPages = Math.max(1, Math.ceil(automationQueueTotal / automationPageLimit));

  async function loadOps() {
    let healthResponse: StoreHealthSummary[] = [];
    if (canRestart) {
      const [overviewResponse, healthItems, metaQueueResponse, billingQueueResponse, automationQueueResponse] = await Promise.all([
        apiFetch<StatusOverview>(`/ops/status/overview${buildQuery({ company_id: companyId })}`),
        apiFetch<StoreHealthSummary[]>(
          `/ops/stores/health${buildQuery({ company_id: companyId, store_id: selectedStoreId })}`
        ),
        apiFetch<MetaWebhookQueuePageRead>(
          `/ops/queue/meta-webhooks${buildQuery({
            company_id: companyId,
            store_id: selectedStoreId,
            status: "retry_scheduled,dead_lettered",
            limit: QUEUE_PAGE_LIMIT_DEFAULT,
            offset: metaQueueOffset,
            order_by: metaQueueOrderBy,
            order_direction: metaQueueOrderDirection
          })}`
        ),
        apiFetch<BillingProviderEventPageRead>(
          `/ops/queue/billing-events${buildQuery({
            company_id: companyId,
            status: "retry_scheduled,dead_lettered",
            limit: QUEUE_PAGE_LIMIT_DEFAULT,
            offset: billingQueueOffset,
            order_by: billingQueueOrderBy,
            order_direction: billingQueueOrderDirection
          })}`
        ),
        apiFetch<AutomationExecutionQueuePageRead>(
          `/ops/queue/automation-executions${buildQuery({
            company_id: companyId,
            store_id: selectedStoreId,
            rule_id: selectedAutomationRuleId,
            channel_id: selectedAutomationChannelId,
            status: selectedAutomationStatus,
            created_from: toStartOfDayIso(automationCreatedFrom),
            created_to: toEndOfDayIso(automationCreatedTo),
            limit: automationPageLimit,
            offset: automationPageOffset,
            order_by: automationOrderBy,
            order_direction: automationOrderDirection
          })}`
        )
      ]);
      healthResponse = healthItems;
      setOverview(overviewResponse);
      setHealth(healthItems);
      setMetaQueue(metaQueueResponse.items);
      setBillingQueue(billingQueueResponse.items);
      setMetaQueueTotal(metaQueueResponse.total);
      setBillingQueueTotal(billingQueueResponse.total);
      setAutomationQueue(automationQueueResponse.items);
      setAutomationQueueTotal(automationQueueResponse.total);
    } else {
      const [overviewResponse, healthItems] = await Promise.all([
        apiFetch<StatusOverview>(`/ops/status/overview${buildQuery({ company_id: companyId })}`),
        apiFetch<StoreHealthSummary[]>(
          `/ops/stores/health${buildQuery({ company_id: companyId, store_id: selectedStoreId })}`
        )
      ]);
      healthResponse = healthItems;
      setOverview(overviewResponse);
      setHealth(healthItems);
      setMetaQueue([]);
      setBillingQueue([]);
      setMetaQueueTotal(0);
      setBillingQueueTotal(0);
      setAutomationQueue([]);
      setAutomationQueueTotal(0);
    }
    if (!detail && healthResponse[0]) {
      await loadDetail(healthResponse[0].store_id);
    }
  }

  async function loadDetail(storeId: string) {
    const response = await apiFetch<StoreHealthDetail>(`/ops/stores/${storeId}/health`);
    setDetail(response);
  }

  async function loadAutomationFilters() {
    if (!canRestart) {
      setAutomationRules([]);
      setAutomationChannels([]);
      setSelectedAutomationRuleId("");
      setSelectedAutomationChannelId("");
      return;
    }

    const [rulesResponse, channelsResponse] = await Promise.all([
      apiFetch<AutomationRuleRead[]>(
        `/automations/rules${buildQuery({ company_id: companyId, store_id: selectedStoreId })}`
      ),
      apiFetch<WhatsAppChannelRead[]>(
        `/channels${buildQuery({ company_id: companyId, store_id: selectedStoreId })}`
      )
    ]);

    setAutomationRules(rulesResponse);
    setAutomationChannels(channelsResponse);
    setSelectedAutomationChannelId((current) =>
      current && channelsResponse.some((channel) => channel.id === current) ? current : ""
    );
    setSelectedAutomationRuleId((current) =>
      current && rulesResponse.some((rule) => rule.id === current) ? current : ""
    );
  }

  useEffect(() => {
    async function load() {
      setError(null);
      try {
        await loadOps();
      } catch (exception) {
        setError(exception instanceof Error ? exception.message : "Falha ao carregar operacao.");
      }
    }
    void load();
  }, [
    apiFetch,
    automationCreatedFrom,
    automationCreatedTo,
    automationOrderBy,
    automationOrderDirection,
    automationPageLimit,
    automationPageOffset,
    companyId,
    billingQueueOffset,
    billingQueueOrderBy,
    billingQueueOrderDirection,
    metaQueueOffset,
    metaQueueOrderBy,
    metaQueueOrderDirection,
    selectedAutomationChannelId,
    selectedAutomationRuleId,
    selectedAutomationStatus,
    selectedStoreId
  ]);

  useEffect(() => {
    async function loadFilters() {
      setError(null);
      try {
        await loadAutomationFilters();
      } catch (exception) {
        setError(exception instanceof Error ? exception.message : "Falha ao carregar filtros de automacao.");
      }
    }
    void loadFilters();
  }, [apiFetch, canRestart, companyId, selectedStoreId]);

  useEffect(() => {
    setSelectedAutomationRuleId((current) =>
      current && filteredAutomationRules.some((rule) => rule.id === current) ? current : ""
    );
  }, [filteredAutomationRules]);

  useEffect(() => {
    setMetaQueueOffset(0);
    setBillingQueueOffset(0);
    setAutomationPageOffset(0);
  }, [
    companyId,
    selectedStoreId,
    metaQueueOrderBy,
    metaQueueOrderDirection,
    billingQueueOrderBy,
    billingQueueOrderDirection,
    selectedAutomationChannelId,
    selectedAutomationRuleId,
    selectedAutomationStatus,
    automationCreatedFrom,
    automationCreatedTo,
    automationOrderBy,
    automationOrderDirection,
    automationPageLimit
  ]);

  useEffect(() => {
    if (metaQueueTotal === 0) {
      if (metaQueueOffset !== 0) {
        setMetaQueueOffset(0);
      }
      return;
    }
    if (metaQueueOffset >= metaQueueTotal) {
      const lastValidOffset = Math.max(0, Math.floor((metaQueueTotal - 1) / QUEUE_PAGE_LIMIT_DEFAULT) * QUEUE_PAGE_LIMIT_DEFAULT);
      if (lastValidOffset !== metaQueueOffset) {
        setMetaQueueOffset(lastValidOffset);
      }
    }
  }, [metaQueueOffset, metaQueueTotal]);

  useEffect(() => {
    if (billingQueueTotal === 0) {
      if (billingQueueOffset !== 0) {
        setBillingQueueOffset(0);
      }
      return;
    }
    if (billingQueueOffset >= billingQueueTotal) {
      const lastValidOffset = Math.max(0, Math.floor((billingQueueTotal - 1) / QUEUE_PAGE_LIMIT_DEFAULT) * QUEUE_PAGE_LIMIT_DEFAULT);
      if (lastValidOffset !== billingQueueOffset) {
        setBillingQueueOffset(lastValidOffset);
      }
    }
  }, [billingQueueOffset, billingQueueTotal]);

  useEffect(() => {
    if (automationQueueTotal === 0) {
      if (automationPageOffset !== 0) {
        setAutomationPageOffset(0);
      }
      return;
    }
    if (automationPageOffset >= automationQueueTotal) {
      const lastValidOffset = Math.max(0, Math.floor((automationQueueTotal - 1) / automationPageLimit) * automationPageLimit);
      if (lastValidOffset !== automationPageOffset) {
        setAutomationPageOffset(lastValidOffset);
      }
    }
  }, [automationPageLimit, automationPageOffset, automationQueueTotal]);

  async function requestRestart() {
    if (!detail || !restartReason.trim()) {
      return;
    }
    setMessage(null);
    setError(null);
    try {
      await apiFetch(`/ops/stores/${detail.store_id}/restart`, {
        method: "POST",
        body: { reason: restartReason.trim(), metadata: { origin: "web_panel" } }
      });
      setRestartReason("");
      setMessage("Restart solicitado para a loja.");
      await loadOps();
      await loadDetail(detail.store_id);
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Falha ao solicitar restart.");
    }
  }

  async function resolveIncident(incidentId: string) {
    if (!detail) {
      return;
    }
    setMessage(null);
    setError(null);
    try {
      await apiFetch(`/ops/incidents/${incidentId}/resolve`, { method: "POST" });
      setMessage("Incidente resolvido.");
      await loadDetail(detail.store_id);
      await loadOps();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Falha ao resolver incidente.");
    }
  }

  async function requeueMeta(eventId: string) {
    setMessage(null);
    setError(null);
    try {
      await apiFetch(`/ops/queue/meta-webhooks/${eventId}/requeue`, { method: "POST" });
      setMessage("Evento Meta reenfileirado.");
      await loadOps();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Falha ao reenfileirar evento Meta.");
    }
  }

  async function requeueBilling(eventId: string) {
    setMessage(null);
    setError(null);
    try {
      await apiFetch(`/ops/queue/billing-events/${eventId}/requeue`, { method: "POST" });
      setMessage("Evento de billing reenfileirado.");
      await loadOps();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Falha ao reenfileirar evento de billing.");
    }
  }

  async function requeueAutomation(executionId: string) {
    setMessage(null);
    setError(null);
    try {
      await apiFetch(`/ops/queue/automation-executions/${executionId}/requeue`, { method: "POST" });
      setMessage("Execucao de automacao reenfileirada.");
      await loadOps();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Falha ao reenfileirar automacao.");
    }
  }

  function clearAutomationFilters() {
    setSelectedAutomationRuleId("");
    setSelectedAutomationChannelId("");
    setSelectedAutomationStatus(AUTOMATION_CRITICAL_STATUS_DEFAULT);
    setAutomationOrderBy("created_at");
    setAutomationOrderDirection("desc");
    setAutomationPageLimit(AUTOMATION_PAGE_LIMIT_DEFAULT);
    setAutomationPageOffset(0);
    setAutomationCreatedFrom("");
    setAutomationCreatedTo("");
  }

  function exportMetaQueueCsv() {
    if (!metaQueue.length) {
      return;
    }

    downloadCsv(
      "ops-meta-queue",
      [
        "event_id",
        "channel_id",
        "company_id",
        "store_id",
        "phone_number_id",
        "processing_status",
        "processing_notes",
        "processing_attempts",
        "last_attempt_at",
        "next_retry_at",
        "dead_lettered_at",
        "processed_at",
        "created_at"
      ],
      metaQueue.map((event) => [
        event.id,
        event.channel_id || "",
        event.company_id || "",
        event.store_id || "",
        event.phone_number_id || "",
        event.processing_status,
        event.processing_notes || "",
        String(event.processing_attempts),
        event.last_attempt_at || "",
        event.next_retry_at || "",
        event.dead_lettered_at || "",
        event.processed_at || "",
        event.created_at
      ])
    );
  }

  function exportBillingQueueCsv() {
    if (!billingQueue.length) {
      return;
    }

    downloadCsv(
      "ops-billing-queue",
      [
        "event_id",
        "company_id",
        "subscription_id",
        "invoice_id",
        "provider_event_id",
        "event_type",
        "processing_status",
        "processing_notes",
        "processing_attempts",
        "last_attempt_at",
        "next_retry_at",
        "dead_lettered_at",
        "processed_at",
        "created_at"
      ],
      billingQueue.map((event) => [
        event.id,
        event.company_id || "",
        event.subscription_id || "",
        event.invoice_id || "",
        event.provider_event_id || "",
        event.event_type,
        event.processing_status,
        event.processing_notes || "",
        String(event.processing_attempts),
        event.last_attempt_at || "",
        event.next_retry_at || "",
        event.dead_lettered_at || "",
        event.processed_at || "",
        event.created_at
      ])
    );
  }

  function exportAutomationQueueCsv() {
    if (!automationQueue.length) {
      return;
    }

    downloadCsv(
      "ops-automation-queue",
      [
        "execution_id",
        "rule_id",
        "rule_name",
        "store_id",
        "channel_id",
        "conversation_id",
        "status",
        "processing_attempts",
        "requested_by_user_name",
        "result_notes",
        "rendered_message",
        "started_at",
        "finished_at",
        "next_retry_at",
        "dead_lettered_at",
        "created_at"
      ],
      automationQueue.map((execution) => [
        execution.id,
        execution.rule_id,
        execution.rule_name,
        execution.store_id,
        execution.channel_id || "",
        execution.conversation_id || "",
        execution.status,
        String(execution.processing_attempts),
        execution.requested_by_user_name || "Sistema",
        execution.result_notes || "",
        execution.rendered_message || "",
        execution.started_at || "",
        execution.finished_at || "",
        execution.next_retry_at || "",
        execution.dead_lettered_at || "",
        execution.created_at
      ])
    );
  }

  return (
    <div className="page-stack">
      <PageHeader
        title="Operacao por loja"
        description="Health checks, runtime, incidentes, filas e restart logico por tenant."
      />

      {message ? <div className="callout callout--success">{message}</div> : null}
      {error ? <div className="callout callout--danger">{error}</div> : null}

      <section className="stats-grid">
        <StatCard label="Online" value={overview?.online_stores ?? 0} tone="teal" helper="Lojas com heartbeat valido" />
        <StatCard label="Degradadas" value={overview?.degraded_stores ?? 0} tone="amber" helper="Falhas recentes sem parada total" />
        <StatCard label="Offline" value={overview?.offline_stores ?? 0} tone="crimson" helper="Sem heartbeat recente" />
        <StatCard label="Restarts pendentes" value={overview?.pending_restarts ?? 0} tone="slate" helper="Pedidos aguardando runtime" />
        <StatCard label="Webhooks falhos" value={overview?.failed_webhooks_24h ?? 0} tone="amber" helper="Ultimas 24h" />
        <StatCard label="Mensagens falhas" value={overview?.failed_messages_24h ?? 0} tone="crimson" helper="Entregas falhas no periodo" />
        <StatCard label="Fila Meta" value={overview?.queued_meta_webhooks ?? 0} tone="slate" helper="Eventos aguardando worker" />
        <StatCard label="Meta em processamento" value={overview?.processing_meta_webhooks ?? 0} tone="teal" helper="Webhooks consumidos agora" />
        <StatCard label="Retry Meta" value={overview?.retry_scheduled_meta_webhooks ?? 0} tone="amber" helper="Eventos aguardando nova tentativa" />
        <StatCard label="Dead-letter Meta" value={overview?.dead_lettered_meta_webhooks ?? 0} tone="crimson" helper="Exigem acao manual" />
        <StatCard label="Fila billing" value={overview?.queued_billing_events ?? 0} tone="slate" helper="Eventos Asaas aguardando worker" />
        <StatCard label="Billing em processamento" value={overview?.processing_billing_events ?? 0} tone="teal" helper="Webhooks financeiros em curso" />
        <StatCard label="Retry billing" value={overview?.retry_scheduled_billing_events ?? 0} tone="amber" helper="Eventos aguardando nova tentativa" />
        <StatCard label="Dead-letter billing" value={overview?.dead_lettered_billing_events ?? 0} tone="crimson" helper="Falhas financeiras persistidas" />
        <StatCard label="Automacoes na fila" value={overview?.queued_automation_executions ?? 0} tone="slate" helper="Execucoes aguardando worker" />
        <StatCard label="Automacoes processando" value={overview?.processing_automation_executions ?? 0} tone="teal" helper="Execucoes em andamento" />
        <StatCard label="Retry automacoes" value={overview?.retry_scheduled_automation_executions ?? 0} tone="amber" helper="Execucoes aguardando nova tentativa" />
        <StatCard label="Dead-letter auto." value={overview?.dead_lettered_automation_executions ?? 0} tone="crimson" helper="Exigem intervencao manual" />
        <StatCard label="Automacoes ignoradas" value={overview?.skipped_automation_executions ?? 0} tone="amber" helper="Regras ignoradas por janela ou escopo" />
      </section>

      <div className="two-column-grid">
        <SectionCard title="Lojas monitoradas" description="Status efetivo calculado a partir do runtime e canais.">
          {health.length ? (
            <div className="timeline-list">
              {health.map((store) => (
                <button
                  key={store.store_id}
                  type="button"
                  className={detail?.store_id === store.store_id ? "mini-panel is-active is-selectable" : "mini-panel is-selectable"}
                  onClick={() => void loadDetail(store.store_id)}
                >
                  <div className="mini-panel__header">
                    <strong>{store.store_name}</strong>
                    <StatusBadge status={store.effective_status} />
                  </div>
                  <p>{store.company_name}</p>
                  <div className="tag-row">
                    <span className="pill">{store.active_channels} canais</span>
                    <span className="pill">{store.unresolved_incidents} incidentes</span>
                    <span className="pill">{store.pending_restarts} restarts</span>
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <EmptyState title="Sem dados operacionais" description="Nenhuma loja retornou status para o filtro atual." />
          )}
        </SectionCard>

        <SectionCard title="Detalhe da loja" description="Runtime, incidentes e restarts recentes.">
          {detail ? (
            <div className="page-stack">
              <div className="tag-row">
                <StatusBadge status={detail.effective_status} />
                <span className="pill">Geracao {detail.runtime_generation}</span>
                <span className="pill">Heartbeat: {formatDateTime(detail.last_heartbeat_at)}</span>
              </div>

              <div className="data-pairs">
                <div>
                  <dt>Version</dt>
                  <dd>{detail.version || "-"}</dd>
                </div>
                <div>
                  <dt>Queue depth</dt>
                  <dd>{detail.queue_depth}</dd>
                </div>
                <div>
                  <dt>Active jobs</dt>
                  <dd>{detail.active_jobs}</dd>
                </div>
                <div>
                  <dt>Backlog</dt>
                  <dd>{detail.backlog_count}</dd>
                </div>
              </div>

              {canRestart ? (
                <>
                  <label>
                    <span>Motivo do restart</span>
                    <textarea value={restartReason} onChange={(event) => setRestartReason(event.target.value)} />
                  </label>
                  <button type="button" className="button button--danger" onClick={() => void requestRestart()}>
                    Solicitar restart da loja
                  </button>
                </>
              ) : null}

              <SectionCard title="Incidentes recentes" description="Alertas ainda abertos ou resolvidos recentemente.">
                {detail.recent_incidents.length ? (
                  <div className="timeline-list">
                    {detail.recent_incidents.map((incident) => (
                      <article key={incident.id} className="mini-panel">
                        <div className="mini-panel__header">
                          <strong>{incident.title}</strong>
                          <StatusBadge status={incident.is_resolved ? "resolved" : incident.severity} />
                        </div>
                        <p>{incident.message || incident.source}</p>
                        {!incident.is_resolved ? (
                          <button type="button" className="button button--secondary" onClick={() => void resolveIncident(incident.id)}>
                            Marcar como resolvido
                          </button>
                        ) : null}
                      </article>
                    ))}
                  </div>
                ) : (
                  <EmptyState title="Sem incidentes" description="Nenhum incidente recente para esta loja." />
                )}
              </SectionCard>

              <JsonBox title="Runtime metadata" value={detail.runtime_state?.metadata || {}} />
            </div>
          ) : (
            <EmptyState title="Selecione uma loja" description="Escolha uma loja para abrir o detalhe operacional." />
          )}
        </SectionCard>
      </div>

      {canRestart ? (
        <div className="three-column-grid">
          <SectionCard title="Fila critica Meta" description="Eventos com retry agendado ou dead-letter.">
            <div className="page-stack">
              <div className="form-grid form-grid--two">
                <label>
                  <span>Ordenar por</span>
                  <select value={metaQueueOrderBy} onChange={(event) => setMetaQueueOrderBy(event.target.value)}>
                    {RETRY_QUEUE_ORDER_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Direcao</span>
                  <select
                    value={metaQueueOrderDirection}
                    onChange={(event) => setMetaQueueOrderDirection(event.target.value)}
                  >
                    <option value="desc">Mais recentes primeiro</option>
                    <option value="asc">Mais antigos primeiro</option>
                  </select>
                </label>
              </div>

              <div className="tag-row">
                <span className="pill">Total: {metaQueueTotal}</span>
                <span className="pill">
                  Pagina {metaCurrentPage} de {metaTotalPages}
                </span>
              </div>

              {metaQueue.length ? (
                <div className="toolbar">
                  <button type="button" className="button button--secondary" onClick={exportMetaQueueCsv}>
                    Exportar CSV
                  </button>
                </div>
              ) : null}

            {metaQueue.length ? (
              <div className="timeline-list">
                {metaQueue.map((event) => (
                  <article key={event.id} className="mini-panel">
                    <div className="mini-panel__header">
                      <strong>{event.phone_number_id || "Sem phone_number_id"}</strong>
                      <StatusBadge status={event.processing_status} />
                    </div>
                    <p>{event.processing_notes}</p>
                    <div className="tag-row">
                      <span className="pill">Attempts {event.processing_attempts}</span>
                      <span className="pill">Proxima: {formatDateTime(event.next_retry_at)}</span>
                    </div>
                    <button type="button" className="button button--secondary" onClick={() => void requeueMeta(event.id)}>
                      Reenfileirar
                    </button>
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState title="Fila Meta saudavel" description="Nenhum evento critico da Meta no momento." />
            )}
              <div className="toolbar">
                <button
                  type="button"
                  className="button button--secondary"
                  onClick={() => setMetaQueueOffset((current) => Math.max(0, current - QUEUE_PAGE_LIMIT_DEFAULT))}
                  disabled={metaQueueOffset <= 0}
                >
                  Pagina anterior
                </button>
                <button
                  type="button"
                  className="button button--secondary"
                  onClick={() => setMetaQueueOffset((current) => current + QUEUE_PAGE_LIMIT_DEFAULT)}
                  disabled={metaQueueOffset + QUEUE_PAGE_LIMIT_DEFAULT >= metaQueueTotal}
                >
                  Proxima pagina
                </button>
              </div>
            </div>
          </SectionCard>

          <SectionCard title="Fila critica Billing" description="Eventos financeiros com retry agendado ou dead-letter.">
            <div className="page-stack">
              <div className="form-grid form-grid--two">
                <label>
                  <span>Ordenar por</span>
                  <select
                    value={billingQueueOrderBy}
                    onChange={(event) => setBillingQueueOrderBy(event.target.value)}
                  >
                    {RETRY_QUEUE_ORDER_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Direcao</span>
                  <select
                    value={billingQueueOrderDirection}
                    onChange={(event) => setBillingQueueOrderDirection(event.target.value)}
                  >
                    <option value="desc">Mais recentes primeiro</option>
                    <option value="asc">Mais antigos primeiro</option>
                  </select>
                </label>
              </div>

              <div className="tag-row">
                <span className="pill">Total: {billingQueueTotal}</span>
                <span className="pill">
                  Pagina {billingCurrentPage} de {billingTotalPages}
                </span>
              </div>

              {billingQueue.length ? (
                <div className="toolbar">
                  <button type="button" className="button button--secondary" onClick={exportBillingQueueCsv}>
                    Exportar CSV
                  </button>
                </div>
              ) : null}

            {billingQueue.length ? (
              <div className="timeline-list">
                {billingQueue.map((event) => (
                  <article key={event.id} className="mini-panel">
                    <div className="mini-panel__header">
                      <strong>{event.event_type}</strong>
                      <StatusBadge status={event.processing_status} />
                    </div>
                    <p>{event.processing_notes}</p>
                    <div className="tag-row">
                      <span className="pill">Attempts {event.processing_attempts}</span>
                      <span className="pill">Proxima: {formatDateTime(event.next_retry_at)}</span>
                    </div>
                    <button type="button" className="button button--secondary" onClick={() => void requeueBilling(event.id)}>
                      Reenfileirar
                    </button>
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState title="Fila billing saudavel" description="Nenhum evento financeiro critico no momento." />
            )}
              <div className="toolbar">
                <button
                  type="button"
                  className="button button--secondary"
                  onClick={() => setBillingQueueOffset((current) => Math.max(0, current - QUEUE_PAGE_LIMIT_DEFAULT))}
                  disabled={billingQueueOffset <= 0}
                >
                  Pagina anterior
                </button>
                <button
                  type="button"
                  className="button button--secondary"
                  onClick={() => setBillingQueueOffset((current) => current + QUEUE_PAGE_LIMIT_DEFAULT)}
                  disabled={billingQueueOffset + QUEUE_PAGE_LIMIT_DEFAULT >= billingQueueTotal}
                >
                  Proxima pagina
                </button>
              </div>
            </div>
          </SectionCard>

          <SectionCard title="Automacoes criticas" description="Execucoes falhas, em processamento prolongado ou ignoradas.">
            <div className="page-stack">
              <div className="form-grid form-grid--two">
                <label>
                  <span>Status</span>
                  <select
                    value={selectedAutomationStatus}
                    onChange={(event) => setSelectedAutomationStatus(event.target.value)}
                  >
                    {AUTOMATION_STATUS_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>

                <label>
                  <span>Ordenar por</span>
                  <select
                    value={automationOrderBy}
                    onChange={(event) => setAutomationOrderBy(event.target.value)}
                  >
                    {AUTOMATION_ORDER_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>

                <label>
                  <span>Filtrar por canal</span>
                  <select
                    value={selectedAutomationChannelId}
                    onChange={(event) => setSelectedAutomationChannelId(event.target.value)}
                  >
                    <option value="">Todos os canais do escopo</option>
                    {automationChannels.map((channel) => (
                      <option key={channel.id} value={channel.id}>
                        {channel.store_name} / {channel.name}
                      </option>
                    ))}
                  </select>
                </label>

                <label>
                  <span>Periodo inicial</span>
                  <input
                    type="date"
                    value={automationCreatedFrom}
                    onChange={(event) => setAutomationCreatedFrom(event.target.value)}
                  />
                </label>

                <label>
                  <span>Periodo final</span>
                  <input
                    type="date"
                    value={automationCreatedTo}
                    onChange={(event) => setAutomationCreatedTo(event.target.value)}
                  />
                </label>

                <label>
                  <span>Direcao</span>
                  <select
                    value={automationOrderDirection}
                    onChange={(event) => setAutomationOrderDirection(event.target.value)}
                  >
                    <option value="desc">Mais recentes primeiro</option>
                    <option value="asc">Mais antigos primeiro</option>
                  </select>
                </label>

                <label className="form-grid__span-2">
                  <span>Filtrar por regra</span>
                  <select
                    value={selectedAutomationRuleId}
                    onChange={(event) => setSelectedAutomationRuleId(event.target.value)}
                  >
                    <option value="">Todas as regras do escopo</option>
                    {filteredAutomationRules.map((rule) => (
                      <option key={rule.id} value={rule.id}>
                        {rule.store_name} / {rule.name}
                        {rule.channel_name ? ` / ${rule.channel_name}` : ""}
                      </option>
                    ))}
                  </select>
                </label>

                <label>
                  <span>Itens por pagina</span>
                  <select
                    value={String(automationPageLimit)}
                    onChange={(event) => setAutomationPageLimit(Number(event.target.value))}
                  >
                    <option value="10">10</option>
                    <option value="20">20</option>
                    <option value="50">50</option>
                  </select>
                </label>
              </div>

              {selectedAutomationChannelId || selectedAutomationRuleId || automationCreatedFrom || automationCreatedTo || selectedAutomationStatus !== AUTOMATION_CRITICAL_STATUS_DEFAULT ? (
                <div className="toolbar">
                  <button
                    type="button"
                    className="button button--secondary"
                    onClick={exportAutomationQueueCsv}
                    disabled={!automationQueue.length}
                  >
                    Exportar CSV
                  </button>
                  <button type="button" className="button button--ghost" onClick={clearAutomationFilters}>
                    Limpar filtros
                  </button>
                </div>
              ) : automationQueue.length ? (
                <div className="toolbar">
                  <button
                    type="button"
                    className="button button--secondary"
                    onClick={exportAutomationQueueCsv}
                  >
                    Exportar CSV
                  </button>
                </div>
              ) : null}

              <div className="tag-row">
                <span className="pill">Total: {automationQueueTotal}</span>
                <span className="pill">
                  Pagina {automationCurrentPage} de {automationTotalPages}
                </span>
              </div>

              {automationQueue.length ? (
                <div className="timeline-list">
                  {automationQueue.map((execution) => (
                    <article key={execution.id} className="mini-panel">
                      <div className="mini-panel__header">
                        <strong>{execution.rule_name}</strong>
                        <StatusBadge status={execution.status} />
                      </div>
                      <p>{execution.result_notes || execution.rendered_message || "Sem detalhes."}</p>
                      <div className="tag-row">
                        <span className="pill">Attempts {execution.processing_attempts}</span>
                        <span className="pill">Solicitado por: {execution.requested_by_user_name || "Sistema"}</span>
                        <span className="pill">Inicio: {formatDateTime(execution.started_at)}</span>
                        <span className="pill">Proxima: {formatDateTime(execution.next_retry_at)}</span>
                      </div>
                      {execution.status !== "processing" ? (
                        <button
                          type="button"
                          className="button button--secondary"
                          onClick={() => void requeueAutomation(execution.id)}
                        >
                          Reenfileirar
                        </button>
                      ) : null}
                    </article>
                  ))}
                </div>
              ) : (
                <EmptyState
                  title="Automacoes saudaveis"
                  description="Nenhuma execucao critica encontrada para o filtro atual."
                />
              )}

              <div className="toolbar">
                <button
                  type="button"
                  className="button button--secondary"
                  onClick={() => setAutomationPageOffset((current) => Math.max(0, current - automationPageLimit))}
                  disabled={automationPageOffset <= 0}
                >
                  Pagina anterior
                </button>
                <button
                  type="button"
                  className="button button--secondary"
                  onClick={() => setAutomationPageOffset((current) => current + automationPageLimit)}
                  disabled={automationPageOffset + automationPageLimit >= automationQueueTotal}
                >
                  Proxima pagina
                </button>
              </div>
            </div>
          </SectionCard>
        </div>
      ) : null}
    </div>
  );
}
