"use client";

import { useEffect, useMemo, useState } from "react";

import { EmptyState } from "@/src/components/EmptyState";
import { PageHeader } from "@/src/components/PageHeader";
import { SectionCard } from "@/src/components/SectionCard";
import { StatCard } from "@/src/components/StatCard";
import { StatusBadge } from "@/src/components/StatusBadge";
import { buildQuery } from "@/src/lib/api";
import { formatCurrency, formatDuration } from "@/src/lib/format";
import { isSuperadmin, resolveScopedCompanyId, resolveScopedStoreId } from "@/src/lib/scope";
import { useAuth } from "@/src/providers/AuthProvider";
import { useWorkspace } from "@/src/providers/WorkspaceProvider";
import type { ConversationSummaryRead, StoreHealthSummary, SubscriptionRead } from "@/src/types/api";

export function ReportsPage() {
  const { apiFetch, user } = useAuth();
  const { companies, stores, selectedCompanyId, selectedStoreId } = useWorkspace();
  const [conversations, setConversations] = useState<ConversationSummaryRead[]>([]);
  const [health, setHealth] = useState<StoreHealthSummary[]>([]);
  const [subscriptions, setSubscriptions] = useState<SubscriptionRead[]>([]);
  const [error, setError] = useState<string | null>(null);

  const companyId = resolveScopedCompanyId(selectedCompanyId, selectedStoreId, stores, companies);
  const storeId = resolveScopedStoreId(selectedStoreId);
  const canViewOps = Boolean(user && (isSuperadmin(user) || user.permissions.includes("ops.view")));
  const canViewBilling = Boolean(user && (isSuperadmin(user) || user.permissions.includes("billing.view")));

  useEffect(() => {
    async function load() {
      setError(null);
      try {
        const [conversationsResponse, healthResponse, subscriptionsResponse] = await Promise.all([
          apiFetch<ConversationSummaryRead[]>(
            `/crm/conversations${buildQuery({ company_id: companyId, store_id: storeId })}`
          ),
          canViewOps
            ? apiFetch<StoreHealthSummary[]>(
                `/ops/stores/health${buildQuery({ company_id: companyId, store_id: storeId })}`
              )
            : Promise.resolve([]),
          canViewBilling
            ? apiFetch<SubscriptionRead[]>(`/billing/subscriptions${buildQuery({ company_id: companyId })}`)
            : Promise.resolve([])
        ]);
        setConversations(conversationsResponse);
        setHealth(healthResponse);
        setSubscriptions(subscriptionsResponse);
      } catch (exception) {
        setError(exception instanceof Error ? exception.message : "Falha ao montar relatorios.");
      }
    }

    void load();
  }, [apiFetch, canViewBilling, canViewOps, companyId, storeId]);

  const averageFirstResponse = useMemo(() => {
    const values = conversations.map((item) => item.first_response_seconds).filter((item): item is number => item !== null);
    if (!values.length) {
      return null;
    }
    return Math.round(values.reduce((sum, item) => sum + item, 0) / values.length);
  }, [conversations]);

  const estimatedMrr = useMemo(
    () =>
      subscriptions
        .filter((item) => ["active", "trialing"].includes(item.status))
        .reduce((sum, item) => sum + item.price_amount, 0),
    [subscriptions]
  );

  return (
    <div className="page-stack">
      <PageHeader
        title="Relatorios operacionais"
        description="Leituras derivadas dos endpoints existentes para atendimento, saude e receita."
      />

      {error ? <div className="callout callout--danger">{error}</div> : null}

      <section className="stats-grid">
        <StatCard label="Conversas" value={conversations.length} tone="slate" helper="Volume carregado no escopo atual" />
        <StatCard label="1a resposta media" value={formatDuration(averageFirstResponse)} tone="teal" helper="Calculado no frontend a partir das conversas" />
        <StatCard label="MRR estimado" value={formatCurrency(estimatedMrr)} tone="amber" helper="Subscriptions active/trialing visiveis" />
        <StatCard label="Lojas degradadas" value={health.filter((item) => item.effective_status === "degraded").length} tone="crimson" helper="Impacto operacional atual" />
      </section>

      <div className="two-column-grid">
        <SectionCard title="Atendimento por loja" description="Contagem de conversas agrupada por store_name.">
          {conversations.length ? (
            <div className="data-table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Loja</th>
                    <th>Conversas</th>
                    <th>Abertas</th>
                    <th>Fechadas</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(
                    conversations.reduce<Record<string, { total: number; open: number; closed: number }>>((acc, item) => {
                      const current = acc[item.store_name] || { total: 0, open: 0, closed: 0 };
                      current.total += 1;
                      if (["closed", "lost", "canceled"].includes(item.status)) {
                        current.closed += 1;
                      } else {
                        current.open += 1;
                      }
                      acc[item.store_name] = current;
                      return acc;
                    }, {})
                  ).map(([storeName, metrics]) => (
                    <tr key={storeName}>
                      <td>{storeName}</td>
                      <td>{metrics.total}</td>
                      <td>{metrics.open}</td>
                      <td>{metrics.closed}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState title="Sem conversas suficientes" description="Nao ha volume carregado para consolidar o relatorio." />
          )}
        </SectionCard>

        <SectionCard title="Health por loja" description="Snapshot do estado operacional mais recente.">
          {health.length ? (
            <div className="timeline-list">
              {health.map((item) => (
                <article key={item.store_id} className="mini-panel">
                  <div className="mini-panel__header">
                    <strong>{item.store_name}</strong>
                    <StatusBadge status={item.effective_status} />
                  </div>
                  <p>{item.company_name}</p>
                  <div className="tag-row">
                    <span className="pill">{item.active_channels} canais</span>
                    <span className="pill">{item.failed_webhooks_24h} webhooks falhos</span>
                    <span className="pill">{item.failed_messages_24h} mensagens falhas</span>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState title="Sem health checks" description="Nenhuma loja retornou dados de saude para este filtro." />
          )}
        </SectionCard>
      </div>
    </div>
  );
}
