"use client";

import { useEffect, useMemo, useState } from "react";

import { EmptyState } from "@/src/components/EmptyState";
import { PageHeader } from "@/src/components/PageHeader";
import { SectionCard } from "@/src/components/SectionCard";
import { StatCard } from "@/src/components/StatCard";
import { StatusBadge } from "@/src/components/StatusBadge";
import { buildQuery } from "@/src/lib/api";
import { formatCurrency, formatDate, formatDateTime, formatDuration } from "@/src/lib/format";
import { isSuperadmin, resolveScopedCompanyId, resolveScopedStoreId } from "@/src/lib/scope";
import { useAuth } from "@/src/providers/AuthProvider";
import { useWorkspace } from "@/src/providers/WorkspaceProvider";
import type { ConversationSummaryRead, StatusOverview, StoreHealthSummary, SubscriptionRead } from "@/src/types/api";

interface DashboardState {
  ops: StatusOverview | null;
  recentConversations: ConversationSummaryRead[];
  storeHealth: StoreHealthSummary[];
  subscriptions: SubscriptionRead[];
}

export function DashboardPage() {
  const { apiFetch, user } = useAuth();
  const { companies, stores, selectedCompanyId, selectedStoreId } = useWorkspace();
  const [state, setState] = useState<DashboardState>({
    ops: null,
    recentConversations: [],
    storeHealth: [],
    subscriptions: []
  });
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const companyId = resolveScopedCompanyId(selectedCompanyId, selectedStoreId, stores, companies);
  const storeId = resolveScopedStoreId(selectedStoreId);
  const canViewOps = Boolean(user && (isSuperadmin(user) || user.permissions.includes("ops.view")));
  const canViewBilling = Boolean(user && (isSuperadmin(user) || user.permissions.includes("billing.view")));

  useEffect(() => {
    async function load() {
      setError(null);
      setIsLoading(true);
      try {
        const [ops, recentConversations, storeHealth, subscriptions] = await Promise.all([
          canViewOps
            ? apiFetch<StatusOverview>(`/ops/status/overview${buildQuery({ company_id: companyId })}`)
            : Promise.resolve(null),
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
        setState({
          ops,
          recentConversations: recentConversations.slice(0, 6),
          storeHealth: storeHealth.slice(0, 6),
          subscriptions
        });
      } catch (exception) {
        setError(exception instanceof Error ? exception.message : "Falha ao carregar dashboard.");
      } finally {
        setIsLoading(false);
      }
    }

    void load();
  }, [apiFetch, canViewBilling, canViewOps, companyId, storeId]);

  const openConversationCount = useMemo(
    () => state.recentConversations.filter((item) => !["closed", "lost", "canceled"].includes(item.status)).length,
    [state.recentConversations]
  );
  const activeSubscriptions = useMemo(
    () => state.subscriptions.filter((item) => ["active", "trialing"].includes(item.status)).length,
    [state.subscriptions]
  );

  return (
    <div className="page-stack">
      <PageHeader
        title="Visao geral da plataforma"
        description="Resumo de operacao, atendimento e receita no escopo ativo."
        meta={
          <>
            <span className="pill">{companies.length} empresas acessiveis</span>
            <span className="pill">{stores.length} lojas acessiveis</span>
            {user ? <span className="pill pill--accent">{user.full_name}</span> : null}
          </>
        }
      />

      {error ? <div className="callout callout--danger">{error}</div> : null}

      <section className="stats-grid">
        <StatCard label="Empresas" value={state.ops?.total_companies ?? companies.length} tone="slate" helper="Clientes visiveis no escopo atual" />
        <StatCard label="Lojas online" value={state.ops?.online_stores ?? 0} tone="teal" helper="Heartbeats e operacao saudavel" />
        <StatCard label="Lojas degradadas" value={state.ops?.degraded_stores ?? 0} tone="amber" helper="Fila, Meta ou runtime com alerta" />
        <StatCard label="Lojas offline" value={state.ops?.offline_stores ?? 0} tone="crimson" helper="Sem heartbeat recente ou runtime parado" />
        <StatCard label="Conversas abertas" value={openConversationCount} tone="teal" helper="Amostra das conversas carregadas agora" />
        <StatCard label="Assinaturas ativas" value={activeSubscriptions} tone="slate" helper="Subscriptions em active ou trialing" />
      </section>

      <div className="two-column-grid">
        <SectionCard title="Atendimentos recentes" description="Conversas mais recentes do escopo selecionado.">
          {isLoading ? (
            <EmptyState title="Carregando conversas" description="Buscando timeline operacional..." />
          ) : state.recentConversations.length ? (
            <div className="data-table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Contato</th>
                    <th>Status</th>
                    <th>Loja</th>
                    <th>Canal</th>
                    <th>1a resposta</th>
                    <th>Atualizacao</th>
                  </tr>
                </thead>
                <tbody>
                  {state.recentConversations.map((conversation) => (
                    <tr key={conversation.id}>
                      <td>
                        <strong>{conversation.contact_name}</strong>
                        <div>{conversation.subject || conversation.contact_phone_number_e164}</div>
                      </td>
                      <td><StatusBadge status={conversation.status} /></td>
                      <td>{conversation.store_name}</td>
                      <td>{conversation.channel.name}</td>
                      <td>{formatDuration(conversation.first_response_seconds)}</td>
                      <td>{formatDateTime(conversation.last_message_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState title="Sem conversas no momento" description="Nenhuma conversa encontrada para o escopo atual." />
          )}
        </SectionCard>

        <SectionCard title="Status por loja" description="Leitura consolidada do runtime e dos canais.">
          {isLoading ? (
            <EmptyState title="Carregando status" description="Conferindo heartbeats e canais..." />
          ) : state.storeHealth.length ? (
            <div className="timeline-list">
              {state.storeHealth.map((item) => (
                <article key={item.store_id} className="mini-panel">
                  <div className="mini-panel__header">
                    <strong>{item.store_name}</strong>
                    <StatusBadge status={item.effective_status} />
                  </div>
                  <p>{item.company_name}</p>
                  <div className="tag-row">
                    <span className="pill">{item.active_channels} canais ativos</span>
                    <span className="pill">{item.unresolved_incidents} incidentes</span>
                    <span className="pill">{item.pending_restarts} restarts</span>
                  </div>
                  <small>Ultimo heartbeat: {formatDateTime(item.last_heartbeat_at)}</small>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState title="Sem status disponivel" description="Nenhuma loja retornou dados operacionais." />
          )}
        </SectionCard>
      </div>

      <SectionCard title="Financeiro resumido" description="Assinaturas carregadas para o escopo atual.">
        {state.subscriptions.length ? (
          <div className="data-table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Subscription</th>
                  <th>Status</th>
                  <th>Ciclo</th>
                  <th>Valor</th>
                  <th>Proximo vencimento</th>
                </tr>
              </thead>
              <tbody>
                {state.subscriptions.slice(0, 8).map((subscription) => (
                  <tr key={subscription.id}>
                    <td>{subscription.id}</td>
                    <td><StatusBadge status={subscription.status} /></td>
                    <td>{subscription.billing_cycle}</td>
                    <td>{formatCurrency(subscription.price_amount)}</td>
                    <td>{formatDate(subscription.next_due_date)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="Sem subscriptions neste escopo" description="Crie uma assinatura na area de billing para comecar a faturar." />
        )}
      </SectionCard>
    </div>
  );
}
