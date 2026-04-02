"use client";

import { useEffect, useMemo, useState } from "react";

import { ChannelBadge } from "@/src/components/ChannelBadge";
import { EmptyState } from "@/src/components/EmptyState";
import { JsonBox } from "@/src/components/JsonBox";
import { PageHeader } from "@/src/components/PageHeader";
import { SectionCard } from "@/src/components/SectionCard";
import { StatusBadge } from "@/src/components/StatusBadge";
import { ApiError, buildQuery } from "@/src/lib/api";
import { formatDateTime } from "@/src/lib/format";
import { resolveScopedCompanyId, resolveScopedStoreId } from "@/src/lib/scope";
import { useAuth } from "@/src/providers/AuthProvider";
import { useWorkspace } from "@/src/providers/WorkspaceProvider";
import type { ChannelCredentialRead, MessageTemplateRead, TemplatesSyncResponse, WhatsAppChannelRead } from "@/src/types/api";

const INITIAL_CHANNEL = {
  name: "",
  code: "",
  display_phone_number: "",
  phone_number_e164: "",
  description: "",
  color_hex: "#16A34A",
  is_default: false,
  support_notes: "",
  status: "active"
};

const INITIAL_CREDENTIAL = {
  phone_number_id: "",
  app_id: "",
  business_account_id: "",
  graph_api_version: "v21.0",
  webhook_callback_url: "",
  access_token: "",
  app_secret: "",
  webhook_verify_token: "",
  is_active: true
};

export function ChannelsPage() {
  const { apiFetch } = useAuth();
  const { companies, stores, selectedCompanyId, selectedStoreId } = useWorkspace();
  const [channels, setChannels] = useState<WhatsAppChannelRead[]>([]);
  const [selected, setSelected] = useState<WhatsAppChannelRead | null>(null);
  const [templates, setTemplates] = useState<MessageTemplateRead[]>([]);
  const [credential, setCredential] = useState<ChannelCredentialRead | null>(null);
  const [channelForm, setChannelForm] = useState(INITIAL_CHANNEL);
  const [credentialForm, setCredentialForm] = useState(INITIAL_CREDENTIAL);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const companyId = resolveScopedCompanyId(selectedCompanyId, selectedStoreId, stores, companies);
  const storeId = resolveScopedStoreId(selectedStoreId);
  const filteredStores = useMemo(
    () => stores.filter((store) => !companyId || store.company_id === companyId),
    [companyId, stores]
  );

  async function loadChannels() {
    const response = await apiFetch<WhatsAppChannelRead[]>(
      `/channels${buildQuery({ company_id: companyId, store_id: storeId })}`
    );
    setChannels(response);
    if (!selected || !response.some((item) => item.id === selected.id)) {
      setSelected(response[0] || null);
    }
  }

  useEffect(() => {
    void loadChannels();
  }, [apiFetch, companyId, storeId]);

  useEffect(() => {
    async function loadChannelMeta() {
      if (!selected) {
        setTemplates([]);
        setCredential(null);
        return;
      }
      try {
        const [templatesResponse, credentialResponse] = await Promise.all([
          apiFetch<MessageTemplateRead[]>(`/meta/channels/${selected.id}/templates`),
          apiFetch<ChannelCredentialRead>(`/meta/channels/${selected.id}/credentials`).catch((exception) => {
            if (exception instanceof ApiError && exception.status === 404) {
              return null;
            }
            throw exception;
          })
        ]);
        setTemplates(templatesResponse);
        setCredential(credentialResponse);
        setCredentialForm((current) => ({
          ...current,
          phone_number_id: credentialResponse?.phone_number_id || selected.external_phone_number_id || "",
          app_id: credentialResponse?.app_id || "",
          business_account_id: credentialResponse?.business_account_id || "",
          graph_api_version: credentialResponse?.graph_api_version || "v21.0",
          webhook_callback_url: credentialResponse?.webhook_callback_url || "",
          is_active: credentialResponse?.is_active ?? true,
          access_token: "",
          app_secret: "",
          webhook_verify_token: ""
        }));
      } catch (exception) {
        setError(exception instanceof Error ? exception.message : "Falha ao carregar integracao Meta.");
      }
    }

    void loadChannelMeta();
  }, [apiFetch, selected]);

  useEffect(() => {
    if (!selected) {
      return;
    }
    setChannelForm({
      name: selected.name,
      code: selected.code,
      display_phone_number: selected.display_phone_number,
      phone_number_e164: selected.phone_number_e164,
      description: selected.description,
      color_hex: selected.color_hex,
      is_default: selected.is_default,
      support_notes: selected.support_notes,
      status: selected.status
    });
  }, [selected]);

  async function handleCreateChannel(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!companyId || !storeId) {
      setError("Selecione empresa e loja para criar um canal.");
      return;
    }
    setMessage(null);
    setError(null);
    try {
      await apiFetch<WhatsAppChannelRead>("/channels", {
        method: "POST",
        body: {
          company_id: companyId,
          store_id: storeId,
          name: channelForm.name,
          code: channelForm.code,
          display_phone_number: channelForm.display_phone_number,
          phone_number_e164: channelForm.phone_number_e164,
          description: channelForm.description,
          color_hex: channelForm.color_hex,
          is_default: channelForm.is_default,
          support_notes: channelForm.support_notes
        }
      });
      setChannelForm(INITIAL_CHANNEL);
      setMessage("Canal criado com sucesso.");
      await loadChannels();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Falha ao criar canal.");
    }
  }

  async function handleUpdateChannel(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) {
      return;
    }
    setMessage(null);
    setError(null);
    try {
      const updated = await apiFetch<WhatsAppChannelRead>(`/channels/${selected.id}`, {
        method: "PATCH",
        body: channelForm
      });
      setSelected(updated);
      setMessage("Canal atualizado.");
      await loadChannels();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Falha ao atualizar canal.");
    }
  }

  async function handleUpsertCredential(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) {
      return;
    }
    setMessage(null);
    setError(null);
    try {
      const payload = {
        phone_number_id: credentialForm.phone_number_id,
        app_id: credentialForm.app_id,
        business_account_id: credentialForm.business_account_id,
        graph_api_version: credentialForm.graph_api_version,
        webhook_callback_url: credentialForm.webhook_callback_url,
        access_token: credentialForm.access_token || null,
        app_secret: credentialForm.app_secret || null,
        webhook_verify_token: credentialForm.webhook_verify_token || null,
        is_active: credentialForm.is_active
      };
      const response = await apiFetch<ChannelCredentialRead>(`/meta/channels/${selected.id}/credentials`, {
        method: "PUT",
        body: payload
      });
      setCredential(response);
      setMessage("Credenciais Meta atualizadas.");
      await loadChannels();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Falha ao salvar credenciais.");
    }
  }

  async function syncTemplates() {
    if (!selected) {
      return;
    }
    setMessage(null);
    setError(null);
    try {
      const response = await apiFetch<TemplatesSyncResponse>(`/meta/channels/${selected.id}/templates/sync`, {
        method: "POST"
      });
      setTemplates(response.templates);
      setMessage(`${response.synced_count} templates sincronizados.`);
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Falha ao sincronizar templates.");
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        title="Canais WhatsApp e Meta"
        description="Gestao de numeros oficiais, credenciais, templates e status por loja."
        meta={
          <>
            <span className="pill">Webhook oficial obrigatório</span>
            <span className="pill pill--accent">Cloud API apenas</span>
          </>
        }
      />

      {message ? <div className="callout callout--success">{message}</div> : null}
      {error ? <div className="callout callout--danger">{error}</div> : null}

      <div className="two-column-grid">
        <SectionCard title="Canais do escopo" description="Separados por empresa e loja.">
          {channels.length ? (
            <div className="timeline-list">
              {channels.map((channel) => (
                <button
                  key={channel.id}
                  type="button"
                  className={selected?.id === channel.id ? "mini-panel is-active is-selectable" : "mini-panel is-selectable"}
                  onClick={() => setSelected(channel)}
                >
                  <div className="mini-panel__header">
                    <ChannelBadge channel={channel} />
                    <StatusBadge status={channel.status} />
                  </div>
                  <p>{channel.company_name} / {channel.store_name}</p>
                  <small>Atualizado em {formatDateTime(channel.updated_at)}</small>
                </button>
              ))}
            </div>
          ) : (
            <EmptyState title="Sem canais cadastrados" description="Cadastre um canal oficial antes de integrar a Meta." />
          )}
        </SectionCard>

        <SectionCard title="Criar canal" description="Vincule o numero oficial a empresa e loja selecionadas.">
          {companyId && storeId ? (
            <form className="form-grid form-grid--two" onSubmit={handleCreateChannel}>
              <label>
                <span>Nome interno</span>
                <input value={channelForm.name} onChange={(event) => setChannelForm((current) => ({ ...current, name: event.target.value }))} required />
              </label>
              <label>
                <span>Codigo</span>
                <input value={channelForm.code} onChange={(event) => setChannelForm((current) => ({ ...current, code: event.target.value }))} required />
              </label>
              <label>
                <span>Numero exibido</span>
                <input value={channelForm.display_phone_number} onChange={(event) => setChannelForm((current) => ({ ...current, display_phone_number: event.target.value }))} required />
              </label>
              <label>
                <span>Numero E.164</span>
                <input value={channelForm.phone_number_e164} onChange={(event) => setChannelForm((current) => ({ ...current, phone_number_e164: event.target.value }))} required />
              </label>
              <label>
                <span>Cor</span>
                <input value={channelForm.color_hex} onChange={(event) => setChannelForm((current) => ({ ...current, color_hex: event.target.value }))} />
              </label>
              <label className="checkbox-row">
                <input type="checkbox" checked={channelForm.is_default} onChange={(event) => setChannelForm((current) => ({ ...current, is_default: event.target.checked }))} />
                <span>Canal padrao da loja</span>
              </label>
              <label className="form-grid__span-2">
                <span>Descricao</span>
                <textarea value={channelForm.description} onChange={(event) => setChannelForm((current) => ({ ...current, description: event.target.value }))} />
              </label>
              <label className="form-grid__span-2">
                <span>Notas de suporte</span>
                <textarea value={channelForm.support_notes} onChange={(event) => setChannelForm((current) => ({ ...current, support_notes: event.target.value }))} />
              </label>
              <div className="form-grid__span-2">
                <button type="submit" className="button button--primary">
                  Criar canal
                </button>
              </div>
            </form>
          ) : (
            <EmptyState title="Selecione empresa e loja" description="Cada canal oficial precisa pertencer a uma loja especifica." />
          )}
        </SectionCard>
      </div>

      {selected ? (
        <div className="two-column-grid">
          <SectionCard title="Dados do canal" description="Ajustes operacionais do numero oficial.">
            <form className="form-grid" onSubmit={handleUpdateChannel}>
              <label>
                <span>Nome interno</span>
                <input value={channelForm.name} onChange={(event) => setChannelForm((current) => ({ ...current, name: event.target.value }))} />
              </label>
              <label>
                <span>Numero exibido</span>
                <input value={channelForm.display_phone_number} onChange={(event) => setChannelForm((current) => ({ ...current, display_phone_number: event.target.value }))} />
              </label>
              <label>
                <span>Status</span>
                <select value={channelForm.status} onChange={(event) => setChannelForm((current) => ({ ...current, status: event.target.value }))}>
                  <option value="active">Ativo</option>
                  <option value="inactive">Inativo</option>
                  <option value="error">Com erro</option>
                </select>
              </label>
              <label>
                <span>Descricao</span>
                <textarea value={channelForm.description} onChange={(event) => setChannelForm((current) => ({ ...current, description: event.target.value }))} />
              </label>
              <button type="submit" className="button button--secondary">
                Salvar canal
              </button>
            </form>
          </SectionCard>

          <SectionCard
            title="Integracao Meta"
            description="Segredos, callback e status de templates aprovados."
            actions={
              <button type="button" className="button button--ghost" onClick={() => void syncTemplates()}>
                Sincronizar templates
              </button>
            }
          >
            <form className="form-grid" onSubmit={handleUpsertCredential}>
              <label>
                <span>Phone Number ID</span>
                <input value={credentialForm.phone_number_id} onChange={(event) => setCredentialForm((current) => ({ ...current, phone_number_id: event.target.value }))} required />
              </label>
              <label>
                <span>App ID</span>
                <input value={credentialForm.app_id} onChange={(event) => setCredentialForm((current) => ({ ...current, app_id: event.target.value }))} required />
              </label>
              <label>
                <span>Business Account ID</span>
                <input value={credentialForm.business_account_id} onChange={(event) => setCredentialForm((current) => ({ ...current, business_account_id: event.target.value }))} required />
              </label>
              <label>
                <span>Versao Graph</span>
                <input value={credentialForm.graph_api_version} onChange={(event) => setCredentialForm((current) => ({ ...current, graph_api_version: event.target.value }))} />
              </label>
              <label>
                <span>Webhook callback URL</span>
                <input value={credentialForm.webhook_callback_url} onChange={(event) => setCredentialForm((current) => ({ ...current, webhook_callback_url: event.target.value }))} required />
              </label>
              <label className="checkbox-row">
                <input type="checkbox" checked={credentialForm.is_active} onChange={(event) => setCredentialForm((current) => ({ ...current, is_active: event.target.checked }))} />
                <span>Credencial ativa</span>
              </label>
              <label>
                <span>Access token</span>
                <input type="password" value={credentialForm.access_token} onChange={(event) => setCredentialForm((current) => ({ ...current, access_token: event.target.value }))} />
              </label>
              <label>
                <span>App secret</span>
                <input type="password" value={credentialForm.app_secret} onChange={(event) => setCredentialForm((current) => ({ ...current, app_secret: event.target.value }))} />
              </label>
              <label>
                <span>Webhook verify token</span>
                <input type="password" value={credentialForm.webhook_verify_token} onChange={(event) => setCredentialForm((current) => ({ ...current, webhook_verify_token: event.target.value }))} />
              </label>
              <button type="submit" className="button button--primary">
                Salvar credenciais
              </button>
            </form>

            {credential ? (
              <div className="page-stack">
                <div className="tag-row">
                  <span className="pill">Ultimo healthcheck: {formatDateTime(credential.last_healthcheck_at)}</span>
                  <span className="pill">Token final: {credential.access_token_last4 || "----"}</span>
                  <StatusBadge status={credential.is_active ? "active" : "inactive"} />
                </div>
                <JsonBox title="Status tecnico" value={credential.status_payload} />
              </div>
            ) : null}
          </SectionCard>
        </div>
      ) : null}

      <SectionCard title="Templates aprovados" description="Disponiveis no canal selecionado depois do sync oficial.">
        {templates.length ? (
          <div className="data-table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Template</th>
                  <th>Idioma</th>
                  <th>Categoria</th>
                  <th>Status</th>
                  <th>Sync</th>
                </tr>
              </thead>
              <tbody>
                {templates.map((template) => (
                  <tr key={template.id}>
                    <td>{template.name}</td>
                    <td>{template.language_code}</td>
                    <td>{template.category}</td>
                    <td><StatusBadge status={template.status} /></td>
                    <td>{formatDateTime(template.last_synced_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="Sem templates sincronizados" description="A sincronizacao depende de credenciais reais da Meta e callback publico HTTPS." />
        )}
      </SectionCard>
    </div>
  );
}
