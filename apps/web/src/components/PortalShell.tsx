"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { buildNavigation } from "@/src/lib/navigation";
import { useAuth } from "@/src/providers/AuthProvider";
import { useWorkspace } from "@/src/providers/WorkspaceProvider";

export function PortalShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const {
    companies,
    visibleStores,
    selectedCompanyId,
    selectedStoreId,
    selectCompany,
    selectStore,
    activeCompany,
    activeStore,
    isLoading
  } = useWorkspace();

  if (!user) {
    return null;
  }

  const navigation = buildNavigation(user);
  const currentRoute = navigation.find((item) => pathname.startsWith(item.href)) || navigation[0];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <span className="brand-block__eyebrow">SaaS WhatsApp Oficial</span>
          <h1>AtendeCRM Platform</h1>
          <p>
            Multiempresa, multiloja, billing recorrente, CRM oficial com Meta e
            monitoramento operacional por tenant.
          </p>
        </div>

        <div className="scope-card">
          <label>
            <span>Empresa em foco</span>
            <select
              value={selectedCompanyId || ""}
              onChange={(event) => selectCompany(event.target.value || null)}
            >
              <option value="">Todas acessiveis</option>
              {companies.map((company) => (
                <option key={company.id} value={company.id}>
                  {company.display_name}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>Loja em foco</span>
            <select
              value={selectedStoreId || ""}
              onChange={(event) => selectStore(event.target.value || null)}
            >
              <option value="">Todas do escopo</option>
              {visibleStores.map((store) => (
                <option key={store.id} value={store.id}>
                  {store.name}
                </option>
              ))}
            </select>
          </label>

          <div className="scope-card__meta">
            <span className="pill">{activeCompany?.display_name || "Visao consolidada"}</span>
            <span className="pill">{activeStore?.name || "Sem loja fixa"}</span>
            {isLoading ? <span className="pill pill--accent">Atualizando escopo</span> : null}
          </div>
        </div>

        <nav className="sidebar__nav">
          {navigation.map((route) => (
            <Link
              key={route.href}
              href={route.href}
              className={pathname.startsWith(route.href) ? "sidebar__link is-active" : "sidebar__link"}
            >
              <span>{route.label}</span>
              <small>{route.hint}</small>
            </Link>
          ))}
        </nav>

        <footer className="sidebar__footer">
          <div className="identity-card">
            <strong>{user.full_name}</strong>
            <span>{user.login}</span>
            <small>
              {user.platform_roles.map((role) => role.role_name).join(", ") || "Escopo corporativo"}
            </small>
          </div>
          <button type="button" className="button button--ghost button--block" onClick={() => void logout()}>
            Encerrar sessao
          </button>
        </footer>
      </aside>

      <div className="workspace">
        <header className="workspace__header">
          <div>
            <span className="workspace__eyebrow">Portal Web</span>
            <h2>{currentRoute.label}</h2>
            <p>{currentRoute.hint}</p>
          </div>
          <div className="workspace__meta">
            <span className="pill">{user.email}</span>
            <span className="pill">{user.permissions.length} permissoes efetivas</span>
            {activeStore ? <span className="pill pill--accent">Loja ativa: {activeStore.name}</span> : null}
          </div>
        </header>
        <main className="workspace__content">{children}</main>
      </div>
    </div>
  );
}
