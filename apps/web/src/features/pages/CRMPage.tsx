"use client";

import { useEffect, useMemo, useState } from "react";

import { ChannelBadge } from "@/src/components/ChannelBadge";
import { EmptyState } from "@/src/components/EmptyState";
import { PageHeader } from "@/src/components/PageHeader";
import { SectionCard } from "@/src/components/SectionCard";
import { StatusBadge } from "@/src/components/StatusBadge";
import { buildQuery } from "@/src/lib/api";
import { formatDateTime, formatDuration, truncate } from "@/src/lib/format";
import { resolveScopedCompanyId, resolveScopedStoreId } from "@/src/lib/scope";
import { useAuth } from "@/src/providers/AuthProvider";
import { useWorkspace } from "@/src/providers/WorkspaceProvider";
import type {
  ContactRead,
  ConversationRead,
  ConversationSummaryRead,
  PlatformUserRead,
  TagRead,
  WhatsAppChannelRead
} from "@/src/types/api";

const INITIAL_CONTACT = {
  full_name: "",
  phone_number_e164: "",
  email: "",
  source: "web",
  notes: ""
};

const INITIAL_CONVERSATION = {
  subject: "",
  priority: "normal",
  source: "whatsapp",
  funnel_stage: ""
};

export function CRMPage() {
  const { apiFetch } = useAuth();
  const { companies, stores, selectedCompanyId, selectedStoreId } = useWorkspace();
  const [contacts, setContacts] = useState<ContactRead[]>([]);
  const [conversations, setConversations] = useState<ConversationSummaryRead[]>([]);
  const [selectedConversation, setSelectedConversation] = useState<ConversationRead | null>(null);
  const [tags, setTags] = useState<TagRead[]>([]);
  const [channels, setChannels] = useState<WhatsAppChannelRead[]>([]);
  const [users, setUsers] = useState<PlatformUserRead[]>([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [contactForm, setContactForm] = useState(INITIAL_CONTACT);
  const [conversationForm, setConversationForm] = useState(INITIAL_CONVERSATION);
  const [selectedContactId, setSelectedContactId] = useState("");
  const [selectedChannelId, setSelectedChannelId] = useState("");
  const [selectedAssigneeId, setSelectedAssigneeId] = useState("");
  const [composerBody, setComposerBody] = useState("");
  const [noteBody, setNoteBody] = useState("");
  const [officialSend, setOfficialSend] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const companyId = resolveScopedCompanyId(selectedCompanyId, selectedStoreId, stores, companies);
  const storeId = resolveScopedStoreId(selectedStoreId);

  async function loadBase() {
    if (!companyId) {
      setContacts([]);
      setConversations([]);
      setTags([]);
      setChannels([]);
      setUsers([]);
      return;
    }
    const [contactsResponse, conversationsResponse, tagsResponse, channelsResponse, usersResponse] =
      await Promise.all([
        apiFetch<ContactRead[]>(`/crm/contacts${buildQuery({ company_id: companyId, store_id: storeId })}`),
        apiFetch<ConversationSummaryRead[]>(
          `/crm/conversations${buildQuery({ company_id: companyId, store_id: storeId, search, status: statusFilter })}`
        ),
        apiFetch<TagRead[]>(`/crm/tags${buildQuery({ company_id: companyId, store_id: storeId })}`),
        apiFetch<WhatsAppChannelRead[]>(`/channels${buildQuery({ company_id: companyId, store_id: storeId })}`),
        apiFetch<PlatformUserRead[]>(`/iam/users${buildQuery({ company_id: companyId, store_id: storeId })}`)
      ]);

    setContacts(contactsResponse);
    setConversations(conversationsResponse);
    setTags(tagsResponse);
    setChannels(channelsResponse);
    setUsers(usersResponse);

    if (!conversationsResponse.length) {
      setSelectedConversation(null);
    } else if (
      selectedConversation &&
      !conversationsResponse.some((conversation) => conversation.id === selectedConversation.id)
    ) {
      setSelectedConversation(null);
    }

    if (!selectedChannelId && channelsResponse[0]) {
      setSelectedChannelId(channelsResponse[0].id);
    }
    if (!selectedContactId && contactsResponse[0]) {
      setSelectedContactId(contactsResponse[0].id);
    }
  }

  useEffect(() => {
    async function load() {
      setError(null);
      try {
        await loadBase();
      } catch (exception) {
        setError(exception instanceof Error ? exception.message : "Falha ao carregar CRM.");
      }
    }

    void load();
  }, [apiFetch, companyId, search, statusFilter, storeId]);

  async function loadConversationDetail(conversationId: string) {
    const detail = await apiFetch<ConversationRead>(`/crm/conversations/${conversationId}`);
    setSelectedConversation(detail);
    setSelectedAssigneeId(detail.assigned_user?.id || "");
  }

  useEffect(() => {
    if (!selectedConversation && conversations[0]) {
      void loadConversationDetail(conversations[0].id);
    }
  }, [conversations, selectedConversation]);

  async function handleCreateContact(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!companyId) {
      setError("Selecione uma empresa para criar o contato.");
      return;
    }
    setError(null);
    setMessage(null);
    try {
      await apiFetch<ContactRead>("/crm/contacts", {
        method: "POST",
        body: {
          company_id: companyId,
          primary_store_id: storeId,
          full_name: contactForm.full_name,
          phone_number_e164: contactForm.phone_number_e164,
          email: contactForm.email || null,
          source: contactForm.source,
          notes: contactForm.notes,
          status: "active",
          tag_ids: []
        }
      });
      setContactForm(INITIAL_CONTACT);
      setMessage("Contato criado.");
      await loadBase();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Falha ao criar contato.");
    }
  }

  async function handleCreateConversation(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!storeId || !selectedChannelId || !selectedContactId) {
      setError("Selecione loja, canal e contato para abrir a conversa.");
      return;
    }
    setError(null);
    setMessage(null);
    try {
      const created = await apiFetch<ConversationRead>("/crm/conversations", {
        method: "POST",
        body: {
          store_id: storeId,
          channel_id: selectedChannelId,
          contact_id: selectedContactId,
          subject: conversationForm.subject,
          priority: conversationForm.priority,
          source: conversationForm.source,
          funnel_stage: conversationForm.funnel_stage,
          assigned_user_id: selectedAssigneeId || null,
          closure_reason: "",
          resolution_notes: "",
          tag_ids: []
        }
      });
      setSelectedConversation(created);
      setConversationForm(INITIAL_CONVERSATION);
      setMessage("Conversa criada.");
      await loadBase();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Falha ao criar conversa.");
    }
  }

  async function handleSendMessage(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedConversation || !composerBody.trim()) {
      return;
    }
    setError(null);
    setMessage(null);
    try {
      if (officialSend) {
        await apiFetch(`/meta/conversations/${selectedConversation.id}/messages/text`, {
          method: "POST",
          body: { body: composerBody.trim(), preview_url: false }
        });
      } else {
        await apiFetch(`/crm/conversations/${selectedConversation.id}/messages`, {
          method: "POST",
          body: {
            direction: "outbound",
            text_body: composerBody.trim(),
            message_type: "text",
            sender_type: "agent",
            delivery_status: "sent",
            metadata: {}
          }
        });
      }
      setComposerBody("");
      setMessage(officialSend ? "Mensagem enviada via Meta." : "Mensagem registrada na timeline.");
      await loadConversationDetail(selectedConversation.id);
      await loadBase();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Falha ao enviar mensagem.");
    }
  }

  async function handleAssignConversation() {
    if (!selectedConversation) {
      return;
    }
    setError(null);
    setMessage(null);
    try {
      const updated = await apiFetch<ConversationRead>(`/crm/conversations/${selectedConversation.id}/assign`, {
        method: "POST",
        body: { assigned_user_id: selectedAssigneeId || null, reason: "Ajuste pelo painel web" }
      });
      setSelectedConversation(updated);
      setMessage("Responsavel atualizado.");
      await loadBase();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Falha ao atualizar responsavel.");
    }
  }

  async function handleStatusChange(nextStatus: string) {
    if (!selectedConversation) {
      return;
    }
    setError(null);
    setMessage(null);
    try {
      const updated = await apiFetch<ConversationRead>(`/crm/conversations/${selectedConversation.id}/status`, {
        method: "POST",
        body: { status: nextStatus, reason: "Mudanca pelo painel web", resolution_notes: null }
      });
      setSelectedConversation(updated);
      setMessage("Status atualizado.");
      await loadBase();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Falha ao alterar status.");
    }
  }

  async function handleAddNote(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedConversation || !noteBody.trim()) {
      return;
    }
    setError(null);
    setMessage(null);
    try {
      await apiFetch(`/crm/conversations/${selectedConversation.id}/notes`, {
        method: "POST",
        body: { note: noteBody.trim() }
      });
      setNoteBody("");
      setMessage("Nota interna adicionada.");
      await loadConversationDetail(selectedConversation.id);
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Falha ao adicionar nota.");
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        title="CRM e atendimento"
        description="Contatos, conversas, timeline operacional e resposta oficial via Meta."
      />

      {message ? <div className="callout callout--success">{message}</div> : null}
      {error ? <div className="callout callout--danger">{error}</div> : null}

      <div className="toolbar">
        <input placeholder="Buscar contato ou telefone" value={search} onChange={(event) => setSearch(event.target.value)} />
        <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
          <option value="">Todos os status</option>
          <option value="new">Nova</option>
          <option value="queued">Em fila</option>
          <option value="in_progress">Em atendimento</option>
          <option value="awaiting_customer">Aguardando cliente</option>
          <option value="closed">Finalizada</option>
        </select>
      </div>

      <div className="conversation-workspace">
        <SectionCard title="Fila de conversas" description="Conversas abertas e finalizadas no escopo atual.">
          {conversations.length ? (
            <div className="timeline-list">
              {conversations.map((conversation) => (
                <button
                  key={conversation.id}
                  type="button"
                  className={selectedConversation?.id === conversation.id ? "conversation-snippet is-active" : "conversation-snippet"}
                  onClick={() => void loadConversationDetail(conversation.id)}
                >
                  <div className="conversation-snippet__top">
                    <strong>{conversation.contact_name}</strong>
                    <StatusBadge status={conversation.status} />
                  </div>
                  <ChannelBadge channel={conversation.channel} />
                  <p>{truncate(conversation.subject || conversation.contact_phone_number_e164, 70)}</p>
                  <div className="conversation-snippet__meta">
                    <span className="pill">{conversation.store_name}</span>
                    <span className="pill">{formatDuration(conversation.first_response_seconds)}</span>
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <EmptyState title="Sem conversas" description="Abra uma nova conversa pelo formulario ao lado." tall />
          )}
        </SectionCard>

        <div className="conversation-center">
          {selectedConversation ? (
            <>
              <div className="conversation-header">
                <div>
                  <h3>{selectedConversation.contact_name}</h3>
                  <p>{selectedConversation.subject || selectedConversation.contact.phone_number_e164}</p>
                </div>
                <div className="conversation-header__meta">
                  <StatusBadge status={selectedConversation.status} />
                  <ChannelBadge channel={selectedConversation.channel} />
                </div>
              </div>

              <SectionCard title="Timeline de mensagens" description="Mensagens registradas ou enviadas pela Cloud API.">
                <div className="message-feed">
                  {selectedConversation.messages.map((messageItem) => (
                    <article
                      key={messageItem.id}
                      className={messageItem.direction === "inbound" ? "message-bubble message-bubble--inbound" : "message-bubble message-bubble--outbound"}
                    >
                      <header>
                        <strong>{messageItem.author_user?.full_name || messageItem.sender_type}</strong>
                        <StatusBadge status={messageItem.delivery_status} />
                      </header>
                      <p>{messageItem.text_body}</p>
                      <footer>
                        <small>{messageItem.message_type}</small>
                        <small>{formatDateTime(messageItem.sent_at)}</small>
                      </footer>
                    </article>
                  ))}
                </div>
              </SectionCard>

              <div className="composer-grid">
                <SectionCard title="Responder cliente" description="Escolha entre envio oficial ou apenas log interno.">
                  <form className="form-grid" onSubmit={handleSendMessage}>
                    <label className="checkbox-row">
                      <input type="checkbox" checked={officialSend} onChange={(event) => setOfficialSend(event.target.checked)} />
                      <span>Enviar pela Cloud API oficial</span>
                    </label>
                    <label>
                      <span>Mensagem</span>
                      <textarea value={composerBody} onChange={(event) => setComposerBody(event.target.value)} />
                    </label>
                    <button type="submit" className="button button--primary">
                      {officialSend ? "Enviar via Meta" : "Registrar na timeline"}
                    </button>
                  </form>
                </SectionCard>

                <SectionCard title="Notas internas" description="Comentarios privados e contexto do atendimento.">
                  <form className="form-grid" onSubmit={handleAddNote}>
                    <label>
                      <span>Nota</span>
                      <textarea value={noteBody} onChange={(event) => setNoteBody(event.target.value)} />
                    </label>
                    <button type="submit" className="button button--secondary">
                      Adicionar nota
                    </button>
                  </form>
                </SectionCard>
              </div>
            </>
          ) : (
            <EmptyState title="Selecione uma conversa" description="A timeline detalhada aparece aqui." tall />
          )}
        </div>

        <SectionCard title="Contexto CRM" description="Contato, atribuicao, eventos e acoes rapidas.">
          {selectedConversation ? (
            <div className="page-stack">
              <div className="tag-row">
                {selectedConversation.tags.map((tag) => <span key={tag.id} className="tag">{tag.name}</span>)}
              </div>

              <dl className="data-pairs">
                <div>
                  <dt>Contato</dt>
                  <dd>{selectedConversation.contact.full_name}</dd>
                </div>
                <div>
                  <dt>Telefone</dt>
                  <dd>{selectedConversation.contact.phone_number_e164}</dd>
                </div>
                <div>
                  <dt>1a resposta</dt>
                  <dd>{formatDuration(selectedConversation.first_response_seconds)}</dd>
                </div>
                <div>
                  <dt>Duracao ativa</dt>
                  <dd>{formatDuration(selectedConversation.active_duration_seconds)}</dd>
                </div>
              </dl>

              <label>
                <span>Responsavel</span>
                <select value={selectedAssigneeId} onChange={(event) => setSelectedAssigneeId(event.target.value)}>
                  <option value="">Fila / sem responsavel</option>
                  {users.map((item) => <option key={item.id} value={item.id}>{item.full_name}</option>)}
                </select>
              </label>
              <button type="button" className="button button--secondary" onClick={() => void handleAssignConversation()}>
                Atualizar responsavel
              </button>

              <div className="toggle-grid">
                {["new", "queued", "in_progress", "awaiting_customer", "closed", "lost"].map((statusValue) => (
                  <button key={statusValue} type="button" className="button button--ghost" onClick={() => void handleStatusChange(statusValue)}>
                    {statusValue}
                  </button>
                ))}
              </div>

              <SectionCard title="Eventos recentes" description="Mudancas de status, atribuicoes e notas.">
                <div className="timeline-list">
                  {selectedConversation.events.slice(0, 8).map((eventItem) => (
                    <article key={eventItem.id} className="timeline-item">
                      <div className="timeline-item__meta">
                        <strong>{eventItem.event_type}</strong>
                        <small>{formatDateTime(eventItem.created_at)}</small>
                      </div>
                      <p>{eventItem.description}</p>
                    </article>
                  ))}
                </div>
              </SectionCard>
            </div>
          ) : (
            <EmptyState title="Sem conversa selecionada" description="Escolha um atendimento para ver o contexto CRM." />
          )}
        </SectionCard>
      </div>

      <div className="two-column-grid">
        <SectionCard title="Novo contato" description="Cadastro rapido dentro da empresa ou loja em foco.">
          {companyId ? (
            <form className="form-grid" onSubmit={handleCreateContact}>
              <label>
                <span>Nome</span>
                <input value={contactForm.full_name} onChange={(event) => setContactForm((current) => ({ ...current, full_name: event.target.value }))} required />
              </label>
              <label>
                <span>Telefone E.164</span>
                <input value={contactForm.phone_number_e164} onChange={(event) => setContactForm((current) => ({ ...current, phone_number_e164: event.target.value }))} required />
              </label>
              <label>
                <span>E-mail</span>
                <input value={contactForm.email} onChange={(event) => setContactForm((current) => ({ ...current, email: event.target.value }))} />
              </label>
              <label>
                <span>Origem</span>
                <input value={contactForm.source} onChange={(event) => setContactForm((current) => ({ ...current, source: event.target.value }))} />
              </label>
              <label>
                <span>Observacoes</span>
                <textarea value={contactForm.notes} onChange={(event) => setContactForm((current) => ({ ...current, notes: event.target.value }))} />
              </label>
              <button type="submit" className="button button--primary">Criar contato</button>
            </form>
          ) : (
            <EmptyState title="Selecione uma empresa" description="O contato precisa ficar vinculado a uma empresa." />
          )}
        </SectionCard>

        <SectionCard title="Nova conversa" description="Abre um atendimento no canal e loja selecionados.">
          {storeId ? (
            <form className="form-grid" onSubmit={handleCreateConversation}>
              <label>
                <span>Contato</span>
                <select value={selectedContactId} onChange={(event) => setSelectedContactId(event.target.value)}>
                  <option value="">Selecione</option>
                  {contacts.map((contact) => <option key={contact.id} value={contact.id}>{contact.full_name}</option>)}
                </select>
              </label>
              <label>
                <span>Canal</span>
                <select value={selectedChannelId} onChange={(event) => setSelectedChannelId(event.target.value)}>
                  <option value="">Selecione</option>
                  {channels.map((channel) => <option key={channel.id} value={channel.id}>{channel.name}</option>)}
                </select>
              </label>
              <label>
                <span>Assunto</span>
                <input value={conversationForm.subject} onChange={(event) => setConversationForm((current) => ({ ...current, subject: event.target.value }))} />
              </label>
              <label>
                <span>Prioridade</span>
                <select value={conversationForm.priority} onChange={(event) => setConversationForm((current) => ({ ...current, priority: event.target.value }))}>
                  <option value="low">Baixa</option>
                  <option value="normal">Normal</option>
                  <option value="high">Alta</option>
                  <option value="urgent">Urgente</option>
                </select>
              </label>
              <button type="submit" className="button button--secondary">Abrir conversa</button>
            </form>
          ) : (
            <EmptyState title="Selecione uma loja" description="Cada conversa precisa pertencer a uma loja e canal." />
          )}
        </SectionCard>
      </div>
    </div>
  );
}
