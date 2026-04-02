"use client";

import { useEffect, useState } from "react";

import { EmptyState } from "@/src/components/EmptyState";
import { JsonBox } from "@/src/components/JsonBox";
import { PageHeader } from "@/src/components/PageHeader";
import { SectionCard } from "@/src/components/SectionCard";
import { buildQuery } from "@/src/lib/api";
import { formatDateTime } from "@/src/lib/format";
import { resolveScopedCompanyId, resolveScopedStoreId } from "@/src/lib/scope";
import { useAuth } from "@/src/providers/AuthProvider";
import { useWorkspace } from "@/src/providers/WorkspaceProvider";
import type { AuditLogRead } from "@/src/types/api";

export function AuditPage() {
  const { apiFetch } = useAuth();
  const { companies, stores, selectedCompanyId, selectedStoreId } = useWorkspace();
  const [logs, setLogs] = useState<AuditLogRead[]>([]);
  const [action, setAction] = useState("");
  const [limit, setLimit] = useState(100);
  const [error, setError] = useState<string | null>(null);

  const companyId = resolveScopedCompanyId(selectedCompanyId, selectedStoreId, stores, companies);
  const storeId = resolveScopedStoreId(selectedStoreId);

  useEffect(() => {
    async function load() {
      setError(null);
      try {
        const response = await apiFetch<AuditLogRead[]>(
          `/ops/audit-logs${buildQuery({ company_id: companyId, store_id: storeId, action, limit })}`
        );
        setLogs(response);
      } catch (exception) {
        setError(exception instanceof Error ? exception.message : "Falha ao carregar auditoria.");
      }
    }

    void load();
  }, [action, apiFetch, companyId, limit, storeId]);

  return (
    <div className="page-stack">
      <PageHeader
        title="Auditoria e trilha de acoes"
        description="Historico administrativo e operacional por empresa, loja e acao."
        actions={
          <div className="toolbar">
            <input placeholder="Filtrar por acao" value={action} onChange={(event) => setAction(event.target.value)} />
            <select value={String(limit)} onChange={(event) => setLimit(Number(event.target.value))}>
              <option value="50">50</option>
              <option value="100">100</option>
              <option value="250">250</option>
              <option value="500">500</option>
            </select>
          </div>
        }
      />

      {error ? <div className="callout callout--danger">{error}</div> : null}

      <SectionCard title="Logs recentes" description="Eventos devolvidos pelo endpoint de auditoria.">
        {logs.length ? (
          <div className="timeline-list">
            {logs.map((log) => (
              <article key={log.id} className="mini-panel">
                <div className="mini-panel__header">
                  <strong>{log.action}</strong>
                  <small>{formatDateTime(log.created_at)}</small>
                </div>
                <p>
                  {log.resource_type} / {log.resource_id}
                </p>
                <div className="tag-row">
                  {log.company_id ? <span className="pill">Empresa: {log.company_id}</span> : null}
                  {log.store_id ? <span className="pill">Loja: {log.store_id}</span> : null}
                  {log.ip_address ? <span className="pill">{log.ip_address}</span> : null}
                </div>
                <JsonBox title="Metadata" value={log.metadata} />
              </article>
            ))}
          </div>
        ) : (
          <EmptyState title="Sem logs" description="Nenhum evento de auditoria encontrado para o filtro atual." />
        )}
      </SectionCard>
    </div>
  );
}
