"use client";

import { useEffect, useMemo, useState } from "react";

import { EmptyState } from "@/src/components/EmptyState";
import { PageHeader } from "@/src/components/PageHeader";
import { SectionCard } from "@/src/components/SectionCard";
import { StatusBadge } from "@/src/components/StatusBadge";
import { buildQuery } from "@/src/lib/api";
import { formatCurrency, formatDate, formatDateTime } from "@/src/lib/format";
import { isSuperadmin, resolveScopedCompanyId, resolveScopedStoreId } from "@/src/lib/scope";
import { useAuth } from "@/src/providers/AuthProvider";
import { useWorkspace } from "@/src/providers/WorkspaceProvider";
import type {
  BillingPlanRead,
  BillingPlanVersionRead,
  CompanyBillingSummary,
  StoreRead,
  SubscriptionRead
} from "@/src/types/api";

const INITIAL_PLAN = { code: "", name: "", description: "" };
const INITIAL_VERSION = {
  billing_scope: "company",
  billing_cycle: "monthly",
  base_amount: 0,
  store_amount: 0,
  user_amount: 0,
  channel_amount: 0,
  included_stores: 1,
  included_users: 3,
  included_channels: 1,
  trial_days: 0,
  is_current: true
};

export function BillingPage() {
  const { apiFetch, user } = useAuth();
  const { companies, stores, selectedCompanyId, selectedStoreId } = useWorkspace();
  const [plans, setPlans] = useState<BillingPlanRead[]>([]);
  const [planVersions, setPlanVersions] = useState<Record<string, BillingPlanVersionRead[]>>({});
  const [subscriptions, setSubscriptions] = useState<SubscriptionRead[]>([]);
  const [summary, setSummary] = useState<CompanyBillingSummary | null>(null);
  const [selectedPlanId, setSelectedPlanId] = useState<string>("");
  const [selectedPlanVersionId, setSelectedPlanVersionId] = useState<string>("");
  const [planForm, setPlanForm] = useState(INITIAL_PLAN);
  const [versionForm, setVersionForm] = useState(INITIAL_VERSION);
  const [paymentMethod, setPaymentMethod] = useState("pix");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const companyId = resolveScopedCompanyId(selectedCompanyId, selectedStoreId, stores, companies);
  const storeId = resolveScopedStoreId(selectedStoreId);
  const canManageBilling = isSuperadmin(user);
  const visibleStores = useMemo(() => stores.filter((item) => !companyId || item.company_id === companyId), [companyId, stores]);

  useEffect(() => {
    setSelectedPlanVersionId("");
  }, [selectedPlanId]);

  useEffect(() => {
    async function load() {
      setError(null);
      try {
        const [plansResponse, subscriptionsResponse, summaryResponse] = await Promise.all([
          apiFetch<BillingPlanRead[]>("/billing/plans"),
          apiFetch<SubscriptionRead[]>(`/billing/subscriptions${buildQuery({ company_id: companyId })}`),
          companyId
            ? apiFetch<CompanyBillingSummary>(`/billing/companies/${companyId}/summary`)
            : Promise.resolve(null)
        ]);
        setPlans(plansResponse);
        setSubscriptions(subscriptionsResponse);
        setSummary(summaryResponse);
        if (!selectedPlanId && plansResponse[0]) {
          setSelectedPlanId(plansResponse[0].id);
        }
      } catch (exception) {
        setError(exception instanceof Error ? exception.message : "Falha ao carregar billing.");
      }
    }

    void load();
  }, [apiFetch, companyId, selectedPlanId]);

  useEffect(() => {
    async function loadVersions() {
      if (!selectedPlanId) {
        return;
      }
      if (planVersions[selectedPlanId]) {
        if (!selectedPlanVersionId && planVersions[selectedPlanId][0]) {
          setSelectedPlanVersionId(planVersions[selectedPlanId][0].id);
        }
        return;
      }
      const versions = await apiFetch<BillingPlanVersionRead[]>(`/billing/plans/${selectedPlanId}/versions`);
      setPlanVersions((current) => ({ ...current, [selectedPlanId]: versions }));
      if (!selectedPlanVersionId && versions[0]) {
        setSelectedPlanVersionId(versions[0].id);
      }
    }

    void loadVersions();
  }, [apiFetch, planVersions, selectedPlanId, selectedPlanVersionId]);

  async function handleCreatePlan(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    setError(null);
    try {
      const plan = await apiFetch<BillingPlanRead>("/billing/plans", { method: "POST", body: planForm });
      setPlans((current) => [...current, plan]);
      setSelectedPlanId(plan.id);
      setPlanForm(INITIAL_PLAN);
      setMessage("Plano criado.");
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Falha ao criar plano.");
    }
  }

  async function handleCreateVersion(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedPlanId) {
      setError("Selecione um plano antes de criar versao.");
      return;
    }
    setMessage(null);
    setError(null);
    try {
      const version = await apiFetch<BillingPlanVersionRead>(`/billing/plans/${selectedPlanId}/versions`, {
        method: "POST",
        body: versionForm
      });
      setPlanVersions((current) => ({
        ...current,
        [selectedPlanId]: [...(current[selectedPlanId] || []), version]
      }));
      setSelectedPlanVersionId(version.id);
      setMessage("Versao de plano criada.");
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Falha ao criar versao.");
    }
  }

  async function handleCreateSubscription(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!companyId || !selectedPlanVersionId) {
      setError("Selecione empresa e versao de plano antes de criar a assinatura.");
      return;
    }
    setMessage(null);
    setError(null);
    try {
      const created = await apiFetch<SubscriptionRead>("/billing/subscriptions", {
        method: "POST",
        body: {
          company_id: companyId,
          store_id: storeId || null,
          plan_version_id: selectedPlanVersionId,
          payment_method: paymentMethod,
          description: "Assinatura criada pelo portal web"
        }
      });
      setSubscriptions((current) => [created, ...current]);
      setMessage("Assinatura criada.");
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Falha ao criar assinatura.");
    }
  }

  async function cancelSubscription(subscriptionId: string) {
    setMessage(null);
    setError(null);
    try {
      const updated = await apiFetch<SubscriptionRead>(`/billing/subscriptions/${subscriptionId}/cancel`, {
        method: "POST"
      });
      setSubscriptions((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setMessage("Assinatura cancelada.");
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Falha ao cancelar assinatura.");
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        title="Billing e assinaturas"
        description="Planos SaaS, subscriptions, historico financeiro e controle comercial."
      />

      {message ? <div className="callout callout--success">{message}</div> : null}
      {error ? <div className="callout callout--danger">{error}</div> : null}

      <div className="two-column-grid">
        <SectionCard title="Resumo da empresa" description="Subscription principal, faturas abertas e pagamentos recentes.">
          {summary ? (
            <div className="page-stack">
              <div className="tag-row">
                <span className="pill">{summary.subscription ? formatCurrency(summary.subscription.price_amount) : "Sem subscription"}</span>
                {summary.subscription ? <StatusBadge status={summary.subscription.status} /> : null}
              </div>
              <div className="data-table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Fatura</th>
                      <th>Status</th>
                      <th>Valor</th>
                      <th>Vencimento</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.open_invoices.slice(0, 6).map((invoice) => (
                      <tr key={invoice.id}>
                        <td>{invoice.description}</td>
                        <td><StatusBadge status={invoice.status} /></td>
                        <td>{formatCurrency(invoice.amount)}</td>
                        <td>{formatDate(invoice.due_date)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <EmptyState title="Selecione uma empresa" description="O resumo financeiro depende de uma empresa em foco." />
          )}
        </SectionCard>

        <SectionCard title="Assinaturas do escopo" description="Company scope ou store scope, conforme o filtro atual.">
          {subscriptions.length ? (
            <div className="timeline-list">
              {subscriptions.map((subscription) => (
                <article key={subscription.id} className="mini-panel">
                  <div className="mini-panel__header">
                    <strong>{subscription.scope}</strong>
                    <StatusBadge status={subscription.status} />
                  </div>
                  <p>{formatCurrency(subscription.price_amount)} / {subscription.billing_cycle}</p>
                  <small>Proximo vencimento: {formatDate(subscription.next_due_date)}</small>
                  {canManageBilling && !["canceled"].includes(subscription.status) ? (
                    <button type="button" className="button button--danger" onClick={() => void cancelSubscription(subscription.id)}>
                      Cancelar assinatura
                    </button>
                  ) : null}
                </article>
              ))}
            </div>
          ) : (
            <EmptyState title="Sem subscriptions" description="Crie a primeira assinatura para faturar esta empresa." />
          )}
        </SectionCard>
      </div>

      {canManageBilling ? (
        <div className="two-column-grid">
          <SectionCard title="Criar plano" description="Catalogo central usado pelo billing da plataforma.">
            <form className="form-grid" onSubmit={handleCreatePlan}>
              <label>
                <span>Codigo</span>
                <input value={planForm.code} onChange={(event) => setPlanForm((current) => ({ ...current, code: event.target.value }))} required />
              </label>
              <label>
                <span>Nome</span>
                <input value={planForm.name} onChange={(event) => setPlanForm((current) => ({ ...current, name: event.target.value }))} required />
              </label>
              <label>
                <span>Descricao</span>
                <textarea value={planForm.description} onChange={(event) => setPlanForm((current) => ({ ...current, description: event.target.value }))} />
              </label>
              <button type="submit" className="button button--primary">Criar plano</button>
            </form>
          </SectionCard>

          <SectionCard title="Criar versao" description="Precificacao por empresa, loja, usuario e canal.">
            <form className="form-grid form-grid--two" onSubmit={handleCreateVersion}>
              <label>
                <span>Plano</span>
                <select value={selectedPlanId} onChange={(event) => setSelectedPlanId(event.target.value)}>
                  <option value="">Selecione</option>
                  {plans.map((plan) => <option key={plan.id} value={plan.id}>{plan.name}</option>)}
                </select>
              </label>
              <label>
                <span>Escopo</span>
                <select value={versionForm.billing_scope} onChange={(event) => setVersionForm((current) => ({ ...current, billing_scope: event.target.value }))}>
                  <option value="company">Empresa</option>
                  <option value="store">Loja</option>
                </select>
              </label>
              <label>
                <span>Ciclo</span>
                <select value={versionForm.billing_cycle} onChange={(event) => setVersionForm((current) => ({ ...current, billing_cycle: event.target.value }))}>
                  <option value="monthly">Mensal</option>
                </select>
              </label>
              <label>
                <span>Valor base</span>
                <input type="number" step="0.01" value={versionForm.base_amount} onChange={(event) => setVersionForm((current) => ({ ...current, base_amount: Number(event.target.value) }))} />
              </label>
              <label>
                <span>Valor por loja</span>
                <input type="number" step="0.01" value={versionForm.store_amount} onChange={(event) => setVersionForm((current) => ({ ...current, store_amount: Number(event.target.value) }))} />
              </label>
              <label>
                <span>Valor por usuario</span>
                <input type="number" step="0.01" value={versionForm.user_amount} onChange={(event) => setVersionForm((current) => ({ ...current, user_amount: Number(event.target.value) }))} />
              </label>
              <label>
                <span>Valor por canal</span>
                <input type="number" step="0.01" value={versionForm.channel_amount} onChange={(event) => setVersionForm((current) => ({ ...current, channel_amount: Number(event.target.value) }))} />
              </label>
              <label>
                <span>Trial em dias</span>
                <input type="number" value={versionForm.trial_days} onChange={(event) => setVersionForm((current) => ({ ...current, trial_days: Number(event.target.value) }))} />
              </label>
              <div className="form-grid__span-2">
                <button type="submit" className="button button--secondary">Criar versao</button>
              </div>
            </form>
          </SectionCard>
        </div>
      ) : null}

      <SectionCard title="Nova assinatura" description="Cria a subscription no provider configurado para a empresa em foco.">
        {companyId ? (
          <form className="form-grid form-grid--two" onSubmit={handleCreateSubscription}>
            <label>
              <span>Versao do plano</span>
              <select value={selectedPlanVersionId} onChange={(event) => setSelectedPlanVersionId(event.target.value)}>
                <option value="">Selecione</option>
                {(planVersions[selectedPlanId] || []).map((version) => (
                  <option key={version.id} value={version.id}>
                    V{version.version_number} - {formatCurrency(version.base_amount)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Metodo de pagamento</span>
              <select value={paymentMethod} onChange={(event) => setPaymentMethod(event.target.value)}>
                <option value="pix">PIX</option>
                <option value="credit_card">Cartao</option>
                <option value="boleto">Boleto</option>
              </select>
            </label>
            <label>
              <span>Loja opcional</span>
              <select value={storeId || ""} disabled>
                <option value="">{storeId ? visibleStores.find((item) => item.id === storeId)?.name : "Escopo empresa"}</option>
              </select>
            </label>
            <div className="form-grid__span-2">
              <button type="submit" className="button button--primary">
                Criar assinatura
              </button>
            </div>
          </form>
        ) : (
          <EmptyState title="Selecione uma empresa" description="A assinatura sempre pertence a uma empresa cliente." />
        )}
      </SectionCard>
    </div>
  );
}
