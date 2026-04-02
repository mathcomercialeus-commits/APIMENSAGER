"use client";

import { useEffect, useMemo, useState } from "react";

import { EmptyState } from "@/src/components/EmptyState";
import { PageHeader } from "@/src/components/PageHeader";
import { SectionCard } from "@/src/components/SectionCard";
import { StatusBadge } from "@/src/components/StatusBadge";
import { formatDateTime } from "@/src/lib/format";
import { isSuperadmin } from "@/src/lib/scope";
import { useAuth } from "@/src/providers/AuthProvider";
import { useWorkspace } from "@/src/providers/WorkspaceProvider";
import type { CompanyRead } from "@/src/types/api";

const INITIAL_CREATE = {
  legal_name: "",
  display_name: "",
  slug: "",
  document_number: "",
  billing_email: ""
};

export function CompaniesPage() {
  const { apiFetch, user } = useAuth();
  const { companies, refreshWorkspace, selectedCompanyId } = useWorkspace();
  const [selected, setSelected] = useState<CompanyRead | null>(null);
  const [createForm, setCreateForm] = useState(INITIAL_CREATE);
  const [updateForm, setUpdateForm] = useState({
    display_name: "",
    legal_name: "",
    billing_email: "",
    status: "active"
  });
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const company = companies.find((item) => item.id === selectedCompanyId) || companies[0] || null;
    setSelected(company);
  }, [companies, selectedCompanyId]);

  useEffect(() => {
    if (!selected) {
      return;
    }
    setUpdateForm({
      display_name: selected.display_name,
      legal_name: selected.legal_name,
      billing_email: selected.billing_email || "",
      status: selected.status
    });
  }, [selected]);

  const canCreate = useMemo(() => isSuperadmin(user), [user]);

  async function handleCreate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    try {
      await apiFetch<CompanyRead>("/companies", {
        method: "POST",
        body: {
          ...createForm,
          document_number: createForm.document_number || null,
          billing_email: createForm.billing_email || null
        }
      });
      setCreateForm(INITIAL_CREATE);
      setMessage("Empresa criada com sucesso.");
      await refreshWorkspace();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Falha ao criar empresa.");
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
      const updated = await apiFetch<CompanyRead>(`/companies/${selected.id}`, {
        method: "PATCH",
        body: {
          display_name: updateForm.display_name,
          legal_name: updateForm.legal_name,
          billing_email: updateForm.billing_email || null,
          status: updateForm.status
        }
      });
      setSelected(updated);
      setMessage("Empresa atualizada.");
      await refreshWorkspace();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Falha ao atualizar empresa.");
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        title="Empresas clientes"
        description="Cadastro das empresas da plataforma e ajuste de status comercial."
      />

      {message ? <div className="callout callout--success">{message}</div> : null}
      {error ? <div className="callout callout--danger">{error}</div> : null}

      <div className="two-column-grid">
        <SectionCard title="Carteira ativa" description="Empresas no escopo do usuario atual.">
          {companies.length ? (
            <div className="timeline-list">
              {companies.map((company) => (
                <button
                  key={company.id}
                  type="button"
                  className={selected?.id === company.id ? "mini-panel is-active is-selectable" : "mini-panel is-selectable"}
                  onClick={() => setSelected(company)}
                >
                  <div className="mini-panel__header">
                    <strong>{company.display_name}</strong>
                    <StatusBadge status={company.status} />
                  </div>
                  <p>{company.legal_name}</p>
                  <small>Criada em {formatDateTime(company.created_at)}</small>
                </button>
              ))}
            </div>
          ) : (
            <EmptyState title="Sem empresas" description="Nenhuma empresa disponivel para este usuario." />
          )}
        </SectionCard>

        <SectionCard title="Detalhes da empresa" description="Atualize nome de exibicao, billing e status da conta.">
          {selected ? (
            <form className="form-grid" onSubmit={handleUpdate}>
              <label>
                <span>Nome fantasia</span>
                <input value={updateForm.display_name} onChange={(event) => setUpdateForm((current) => ({ ...current, display_name: event.target.value }))} />
              </label>
              <label>
                <span>Razao social</span>
                <input value={updateForm.legal_name} onChange={(event) => setUpdateForm((current) => ({ ...current, legal_name: event.target.value }))} />
              </label>
              <label>
                <span>E-mail de cobranca</span>
                <input type="email" value={updateForm.billing_email} onChange={(event) => setUpdateForm((current) => ({ ...current, billing_email: event.target.value }))} />
              </label>
              <label>
                <span>Status</span>
                <select value={updateForm.status} onChange={(event) => setUpdateForm((current) => ({ ...current, status: event.target.value }))}>
                  <option value="active">Ativa</option>
                  <option value="trial">Trial</option>
                  <option value="past_due">Em atraso</option>
                  <option value="suspended">Suspensa</option>
                  <option value="blocked">Bloqueada</option>
                </select>
              </label>
              <button type="submit" className="button button--primary">
                Salvar alteracoes
              </button>
            </form>
          ) : (
            <EmptyState title="Selecione uma empresa" description="Escolha uma empresa para editar os dados." />
          )}
        </SectionCard>
      </div>

      {canCreate ? (
        <SectionCard title="Nova empresa" description="Disponivel apenas para superadmin da plataforma.">
          <form className="form-grid form-grid--two" onSubmit={handleCreate}>
            <label>
              <span>Razao social</span>
              <input value={createForm.legal_name} onChange={(event) => setCreateForm((current) => ({ ...current, legal_name: event.target.value }))} required />
            </label>
            <label>
              <span>Nome fantasia</span>
              <input value={createForm.display_name} onChange={(event) => setCreateForm((current) => ({ ...current, display_name: event.target.value }))} required />
            </label>
            <label>
              <span>Slug</span>
              <input value={createForm.slug} onChange={(event) => setCreateForm((current) => ({ ...current, slug: event.target.value }))} required />
            </label>
            <label>
              <span>Documento</span>
              <input value={createForm.document_number} onChange={(event) => setCreateForm((current) => ({ ...current, document_number: event.target.value }))} />
            </label>
            <label className="form-grid__span-2">
              <span>E-mail de cobranca</span>
              <input type="email" value={createForm.billing_email} onChange={(event) => setCreateForm((current) => ({ ...current, billing_email: event.target.value }))} />
            </label>
            <div className="form-grid__span-2">
              <button type="submit" className="button button--primary">
                Criar empresa
              </button>
            </div>
          </form>
        </SectionCard>
      ) : null}
    </div>
  );
}
