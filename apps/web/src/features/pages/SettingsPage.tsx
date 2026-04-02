"use client";

import { PageHeader } from "@/src/components/PageHeader";
import { SectionCard } from "@/src/components/SectionCard";
import { JsonBox } from "@/src/components/JsonBox";
import { getApiBaseUrl } from "@/src/lib/api";
import { useAuth } from "@/src/providers/AuthProvider";
import { useWorkspace } from "@/src/providers/WorkspaceProvider";

export function SettingsPage() {
  const { user } = useAuth();
  const { activeCompany, activeStore, companies, stores } = useWorkspace();

  return (
    <div className="page-stack">
      <PageHeader
        title="Configuracoes e contexto"
        description="Resumo da sessao atual, escopo ativo e parametros operacionais do portal."
      />

      <div className="two-column-grid">
        <SectionCard title="Sessao atual" description="Dados do usuario autenticado e permissões efetivas.">
          {user ? (
            <div className="page-stack">
              <div className="tag-row">
                <span className="pill">{user.full_name}</span>
                <span className="pill">{user.login}</span>
                <span className="pill pill--accent">{user.email}</span>
              </div>
              <div className="data-pairs">
                <div>
                  <dt>Empresas acessiveis</dt>
                  <dd>{companies.length}</dd>
                </div>
                <div>
                  <dt>Lojas acessiveis</dt>
                  <dd>{stores.length}</dd>
                </div>
                <div>
                  <dt>Empresa ativa</dt>
                  <dd>{activeCompany?.display_name || "Visao consolidada"}</dd>
                </div>
                <div>
                  <dt>Loja ativa</dt>
                  <dd>{activeStore?.name || "Sem loja fixa"}</dd>
                </div>
              </div>
              <JsonBox title="Permissoes efetivas" value={user.permissions} />
            </div>
          ) : null}
        </SectionCard>

        <SectionCard title="Parametros do frontend" description="Configuracao atual do portal web e da integracao com a API.">
          <div className="page-stack">
            <div className="tag-row">
              <span className="pill">API base</span>
              <code>{getApiBaseUrl()}</code>
            </div>
            <div className="callout callout--info">
              As configuracoes operacionais de empresa, loja, billing e Meta ficam distribuidas
              nas telas especificas deste portal. Esta pagina consolida apenas o contexto da sessao.
            </div>
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
