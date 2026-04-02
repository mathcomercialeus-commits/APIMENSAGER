"use client";

import { useEffect, useMemo, useState } from "react";

import { EmptyState } from "@/src/components/EmptyState";
import { PageHeader } from "@/src/components/PageHeader";
import { SectionCard } from "@/src/components/SectionCard";
import { StatusBadge } from "@/src/components/StatusBadge";
import { formatDateTime } from "@/src/lib/format";
import { resolveScopedCompanyId } from "@/src/lib/scope";
import { useAuth } from "@/src/providers/AuthProvider";
import { useWorkspace } from "@/src/providers/WorkspaceProvider";
import type { StoreRead } from "@/src/types/api";

const INITIAL_CREATE = {
  name: "",
  code: "",
  slug: "",
  timezone: "America/Manaus"
};

export function StoresPage() {
  const { apiFetch } = useAuth();
  const { companies, stores, selectedCompanyId, selectedStoreId, refreshWorkspace } = useWorkspace();
  const [selected, setSelected] = useState<StoreRead | null>(null);
  const [createForm, setCreateForm] = useState(INITIAL_CREATE);
  const [updateForm, setUpdateForm] = useState({
    name: "",
    timezone: "America/Manaus",
    status: "active",
    heartbeat_enabled: true,
    support_notes: ""
  });
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const companyId = resolveScopedCompanyId(selectedCompanyId, selectedStoreId, stores, companies);
  const filteredStores = useMemo(
    () => stores.filter((store) => !companyId || store.company_id === companyId),
    [companyId, stores]
  );

  useEffect(() => {
    const store = filteredStores.find((item) => item.id === selectedStoreId) || filteredStores[0] || null;
    setSelected(store);
  }, [filteredStores, selectedStoreId]);

  useEffect(() => {
    if (!selected) {
      return;
    }
    setUpdateForm({
      name: selected.name,
      timezone: selected.timezone,
      status: selected.status,
      heartbeat_enabled: selected.heartbeat_enabled,
      support_notes: selected.support_notes
    });
  }, [selected]);

  async function handleCreate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!companyId) {
      setError("Selecione uma empresa para criar a loja.");
      return;
    }
    setError(null);
    setMessage(null);
    try {
      await apiFetch<StoreRead>(`/stores/company/${companyId}`, { method: "POST", body: createForm });
      setCreateForm(INITIAL_CREATE);
      setMessage("Loja criada com sucesso.");
      await refreshWorkspace();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Falha ao criar loja.");
    }
  }

  async function handleUpdate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) {
      return;
    }
    setError(null);
    setMessage(null);
    try {
      const updated = await apiFetch<StoreRead>(`/stores/${selected.id}`, {
        method: "PATCH",
        body: updateForm
      });
      setSelected(updated);
      setMessage("Loja atualizada.");
      await refreshWorkspace();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Falha ao atualizar loja.");
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        title="Lojas e unidades"
        description="Heartbeat, timezone, status operacional e cadastro das lojas por empresa."
      />

      {message ? <div className="callout callout--success">{message}</div> : null}
      {error ? <div className="callout callout--danger">{error}</div> : null}

      <div className="two-column-grid">
        <SectionCard title="Lojas visiveis" description="Filtradas pela empresa em foco.">
          {filteredStores.length ? (
            <div className="timeline-list">
              {filteredStores.map((store) => (
                <button
                  key={store.id}
                  type="button"
                  className={selected?.id === store.id ? "mini-panel is-active is-selectable" : "mini-panel is-selectable"}
                  onClick={() => setSelected(store)}
                >
                  <div className="mini-panel__header">
                    <strong>{store.name}</strong>
                    <StatusBadge status={store.status} />
                  </div>
                  <p>{store.company_name}</p>
                  <div className="tag-row">
                    <span className="pill">{store.code}</span>
                    <span className="pill">{store.timezone}</span>
                    {store.heartbeat_enabled ? <span className="pill pill--accent">Heartbeat ativo</span> : null}
                  </div>
                  <small>Atualizada em {formatDateTime(store.updated_at)}</small>
                </button>
              ))}
            </div>
          ) : (
            <EmptyState title="Sem lojas" description="Nao ha lojas no escopo atual." />
          )}
        </SectionCard>

        <SectionCard title="Detalhes da loja" description="Ajuste de status, timezone e observacoes internas.">
          {selected ? (
            <form className="form-grid" onSubmit={handleUpdate}>
              <label>
                <span>Nome</span>
                <input value={updateForm.name} onChange={(event) => setUpdateForm((current) => ({ ...current, name: event.target.value }))} />
              </label>
              <label>
                <span>Timezone</span>
                <input value={updateForm.timezone} onChange={(event) => setUpdateForm((current) => ({ ...current, timezone: event.target.value }))} />
              </label>
              <label>
                <span>Status</span>
                <select value={updateForm.status} onChange={(event) => setUpdateForm((current) => ({ ...current, status: event.target.value }))}>
                  <option value="active">Ativa</option>
                  <option value="inactive">Inativa</option>
                  <option value="suspended">Suspensa</option>
                </select>
              </label>
              <label className="checkbox-row">
                <input type="checkbox" checked={updateForm.heartbeat_enabled} onChange={(event) => setUpdateForm((current) => ({ ...current, heartbeat_enabled: event.target.checked }))} />
                <span>Heartbeat habilitado</span>
              </label>
              <label>
                <span>Notas de suporte</span>
                <textarea value={updateForm.support_notes} onChange={(event) => setUpdateForm((current) => ({ ...current, support_notes: event.target.value }))} />
              </label>
              <button type="submit" className="button button--primary">
                Salvar loja
              </button>
            </form>
          ) : (
            <EmptyState title="Selecione uma loja" description="Escolha uma loja para editar os detalhes." />
          )}
        </SectionCard>
      </div>

      <SectionCard title="Nova loja" description="Cadastro rapido de unidade na empresa atualmente selecionada.">
        {companyId ? (
          <form className="form-grid form-grid--two" onSubmit={handleCreate}>
            <label>
              <span>Nome</span>
              <input value={createForm.name} onChange={(event) => setCreateForm((current) => ({ ...current, name: event.target.value }))} required />
            </label>
            <label>
              <span>Codigo interno</span>
              <input value={createForm.code} onChange={(event) => setCreateForm((current) => ({ ...current, code: event.target.value }))} required />
            </label>
            <label>
              <span>Slug</span>
              <input value={createForm.slug} onChange={(event) => setCreateForm((current) => ({ ...current, slug: event.target.value }))} required />
            </label>
            <label>
              <span>Timezone</span>
              <input value={createForm.timezone} onChange={(event) => setCreateForm((current) => ({ ...current, timezone: event.target.value }))} />
            </label>
            <div className="form-grid__span-2">
              <button type="submit" className="button button--primary">
                Criar loja
              </button>
            </div>
          </form>
        ) : (
          <EmptyState title="Selecione uma empresa" description="A criacao de loja exige empresa em foco." />
        )}
      </SectionCard>
    </div>
  );
}
