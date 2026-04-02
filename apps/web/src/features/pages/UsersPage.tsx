"use client";

import { useEffect, useMemo, useState } from "react";

import { EmptyState } from "@/src/components/EmptyState";
import { PageHeader } from "@/src/components/PageHeader";
import { SectionCard } from "@/src/components/SectionCard";
import { StatusBadge } from "@/src/components/StatusBadge";
import { buildQuery } from "@/src/lib/api";
import { isSuperadmin, resolveScopedCompanyId, resolveScopedStoreId } from "@/src/lib/scope";
import { useAuth } from "@/src/providers/AuthProvider";
import { useWorkspace } from "@/src/providers/WorkspaceProvider";
import type { PlatformUserRead, RoleRead } from "@/src/types/api";

const INITIAL_USER = {
  full_name: "",
  login: "",
  email: "",
  password: "",
  must_change_password: true
};

export function UsersPage() {
  const { apiFetch, user } = useAuth();
  const { companies, stores, selectedCompanyId, selectedStoreId } = useWorkspace();
  const [users, setUsers] = useState<PlatformUserRead[]>([]);
  const [roles, setRoles] = useState<RoleRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState(INITIAL_USER);
  const [companyMembershipRole, setCompanyMembershipRole] = useState("company_admin");
  const [storeMembershipRole, setStoreMembershipRole] = useState("store_manager");

  const companyId = resolveScopedCompanyId(selectedCompanyId, selectedStoreId, stores, companies);
  const storeId = resolveScopedStoreId(selectedStoreId);
  const canCreateUser = isSuperadmin(user);

  const companyRoles = useMemo(() => roles.filter((item) => item.scope_level === "company"), [roles]);
  const storeRoles = useMemo(() => roles.filter((item) => item.scope_level === "store"), [roles]);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [rolesResponse, usersResponse] = await Promise.all([
          apiFetch<RoleRead[]>("/iam/roles"),
          apiFetch<PlatformUserRead[]>(`/iam/users${buildQuery({ company_id: companyId, store_id: storeId })}`)
        ]);
        setRoles(rolesResponse);
        setUsers(usersResponse);
      } catch (exception) {
        setError(exception instanceof Error ? exception.message : "Falha ao carregar usuarios.");
      } finally {
        setLoading(false);
      }
    }

    if (canCreateUser || companyId || storeId) {
      void load();
    }
  }, [apiFetch, canCreateUser, companyId, storeId]);

  async function handleCreateUser(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    setError(null);
    try {
      const created = await apiFetch<PlatformUserRead>("/iam/users", {
        method: "POST",
        body: createForm
      });
      setUsers((current) => [created, ...current]);
      setCreateForm(INITIAL_USER);
      setMessage("Usuario criado com sucesso.");
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Falha ao criar usuario.");
    }
  }

  async function grantCompanyMembership(userId: string) {
    if (!companyId) {
      setError("Selecione uma empresa antes de conceder membership.");
      return;
    }
    setError(null);
    setMessage(null);
    try {
      const updated = await apiFetch<PlatformUserRead>("/iam/company-memberships", {
        method: "POST",
        body: { user_id: userId, company_id: companyId, role_code: companyMembershipRole }
      });
      setUsers((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setMessage("Membership de empresa concedido.");
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Falha ao conceder membership.");
    }
  }

  async function grantStoreMembership(userId: string) {
    if (!storeId) {
      setError("Selecione uma loja antes de conceder membership.");
      return;
    }
    setError(null);
    setMessage(null);
    try {
      const updated = await apiFetch<PlatformUserRead>("/iam/store-memberships", {
        method: "POST",
        body: { user_id: userId, store_id: storeId, role_code: storeMembershipRole }
      });
      setUsers((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setMessage("Membership de loja concedido.");
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Falha ao conceder membership.");
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        title="Usuarios, RBAC e memberships"
        description="Gestao de equipe por empresa e loja, alinhada ao controle de acesso do backend."
      />

      {message ? <div className="callout callout--success">{message}</div> : null}
      {error ? <div className="callout callout--danger">{error}</div> : null}

      {canCreateUser ? (
        <SectionCard title="Criar usuario global" description="Fluxo reservado ao superadmin da plataforma.">
          <form className="form-grid form-grid--two" onSubmit={handleCreateUser}>
            <label>
              <span>Nome completo</span>
              <input value={createForm.full_name} onChange={(event) => setCreateForm((current) => ({ ...current, full_name: event.target.value }))} required />
            </label>
            <label>
              <span>Login</span>
              <input value={createForm.login} onChange={(event) => setCreateForm((current) => ({ ...current, login: event.target.value }))} required />
            </label>
            <label>
              <span>E-mail</span>
              <input type="email" value={createForm.email} onChange={(event) => setCreateForm((current) => ({ ...current, email: event.target.value }))} required />
            </label>
            <label>
              <span>Senha inicial</span>
              <input type="password" value={createForm.password} onChange={(event) => setCreateForm((current) => ({ ...current, password: event.target.value }))} required />
            </label>
            <label className="checkbox-row form-grid__span-2">
              <input type="checkbox" checked={createForm.must_change_password} onChange={(event) => setCreateForm((current) => ({ ...current, must_change_password: event.target.checked }))} />
              <span>Exigir troca de senha no primeiro acesso</span>
            </label>
            <div className="form-grid__span-2">
              <button type="submit" className="button button--primary">
                Criar usuario
              </button>
            </div>
          </form>
        </SectionCard>
      ) : null}

      <div className="two-column-grid">
        <SectionCard title="Usuarios do escopo" description="Lista calculada a partir da empresa ou loja em foco.">
          {loading ? (
            <EmptyState title="Carregando usuarios" description="Buscando memberships e roles..." />
          ) : users.length ? (
            <div className="timeline-list">
              {users.map((item) => (
                <article key={item.id} className="mini-panel">
                  <div className="mini-panel__header">
                    <strong>{item.full_name}</strong>
                    <StatusBadge status={item.status} />
                  </div>
                  <p>{item.email}</p>
                  <div className="tag-row">
                    {item.platform_roles.map((role) => <span key={role.role_code} className="pill">{role.role_name}</span>)}
                    {item.company_memberships.map((membership) => <span key={membership.company_id} className="pill pill--accent">{membership.company_name}: {membership.role.role_name}</span>)}
                    {item.store_memberships.map((membership) => <span key={membership.store_id} className="pill">{membership.store_name}: {membership.role.role_name}</span>)}
                  </div>
                  <div className="toolbar">
                    {companyId ? (
                      <>
                        <select value={companyMembershipRole} onChange={(event) => setCompanyMembershipRole(event.target.value)}>
                          {companyRoles.map((role) => <option key={role.id} value={role.code}>{role.name}</option>)}
                        </select>
                        <button type="button" className="button button--secondary" onClick={() => void grantCompanyMembership(item.id)}>
                          Vincular a empresa
                        </button>
                      </>
                    ) : null}
                    {storeId ? (
                      <>
                        <select value={storeMembershipRole} onChange={(event) => setStoreMembershipRole(event.target.value)}>
                          {storeRoles.map((role) => <option key={role.id} value={role.code}>{role.name}</option>)}
                        </select>
                        <button type="button" className="button button--ghost" onClick={() => void grantStoreMembership(item.id)}>
                          Vincular a loja
                        </button>
                      </>
                    ) : null}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState title="Sem usuarios no escopo" description="Selecione empresa ou loja para listar os usuarios com membership." />
          )}
        </SectionCard>

        <SectionCard title="Roles disponiveis" description="Papeis retornados pelo backend para company e store scopes.">
          {roles.length ? (
            <div className="timeline-list">
              {roles.map((role) => (
                <article key={role.id} className="mini-panel">
                  <div className="mini-panel__header">
                    <strong>{role.name}</strong>
                    <span className="pill">{role.scope_level}</span>
                  </div>
                  <p>{role.description}</p>
                  <div className="tag-row">
                    {role.permissions.slice(0, 8).map((permission) => <span key={permission.id} className="tag">{permission.code}</span>)}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState title="Sem roles" description="As roles ainda nao foram carregadas para este escopo." />
          )}
        </SectionCard>
      </div>
    </div>
  );
}
