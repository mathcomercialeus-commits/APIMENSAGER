# ETAPA 1 - Modelo de Banco SaaS

## Principios

- banco unico PostgreSQL
- controle global em `public`
- dados operacionais tenant-aware em `crm`
- `company_id` e `store_id` obrigatorios conforme o dominio
- soft delete onde fizer sentido
- particionamento para alto volume

## Entidades principais

### Controle da plataforma

- `platform_users`
- `platform_user_sessions`
- `platform_roles`
- `platform_permissions`
- `platform_user_roles`
- `client_companies`
- `stores`
- `store_domains`
- `company_memberships`
- `store_memberships`

### Billing

- `billing_plans`
- `billing_plan_versions`
- `subscriptions`
- `subscription_items`
- `invoices`
- `payments`
- `payment_events`
- `billing_customers`
- `dunning_policies`
- `credit_notes`

### Meta e canais

- `whatsapp_channels`
- `channel_credentials`
- `channel_templates`
- `meta_webhook_events`
- `channel_health`
- `meta_api_call_logs`

### CRM e atendimento

- `contacts`
- `contact_tags`
- `tags`
- `conversations`
- `conversation_messages`
- `conversation_events`
- `conversation_assignments`
- `conversation_notes`
- `pipelines`
- `pipeline_stages`

### Operacao e automacao

- `automation_rules`
- `automation_runs`
- `queue_jobs`
- `store_runtime_states`
- `store_health_checks`
- `system_status`
- `usage_metrics`
- `notifications`
- `incident_events`
- `restart_events`

### Auditoria

- `audit_logs`
- `security_events`
- `support_actions`

## Modelagem recomendada

### `client_companies`

- `id`
- `legal_name`
- `display_name`
- `document_number`
- `status`
- `trial_ends_at`
- `suspension_reason`
- `created_at`
- `updated_at`

### `stores`

- `id`
- `company_id`
- `name`
- `code`
- `timezone`
- `status`
- `billing_scope`
- `created_at`
- `updated_at`

Indices:

- `(company_id, status)`
- `(company_id, code)` unico

### `subscriptions`

- `id`
- `company_id`
- `store_id` nullable
- `plan_version_id`
- `provider`
- `provider_subscription_id`
- `status`
- `billing_cycle`
- `trial_ends_at`
- `current_period_start`
- `current_period_end`
- `grace_ends_at`
- `canceled_at`

Indices:

- `(company_id, status)`
- `(store_id, status)`

### `whatsapp_channels`

- `id`
- `company_id`
- `store_id`
- `display_name`
- `phone_number`
- `phone_number_id`
- `waba_id`
- `status`
- `quality_rating`
- `created_at`
- `updated_at`

Indices:

- `(store_id, status)`
- `(phone_number_id)` unico

### `conversations`

- `id`
- `company_id`
- `store_id`
- `channel_id`
- `contact_id`
- `assigned_user_id`
- `status`
- `first_inbound_at`
- `first_human_reply_at`
- `opened_at`
- `closed_at`
- `last_message_at`
- `sla_first_response_seconds`
- `sla_resolution_seconds`

Indices:

- `(store_id, status, last_message_at desc)`
- `(company_id, last_message_at desc)`
- `(channel_id, status)`

### `conversation_messages`

- `id`
- `company_id`
- `store_id`
- `conversation_id`
- `channel_id`
- `meta_message_id`
- `direction`
- `message_type`
- `status`
- `sent_at`
- `delivered_at`
- `read_at`
- `failed_at`
- `payload_json`

Particionamento recomendado:

- por mes em `sent_at`

### `store_runtime_states`

- `store_id`
- `runtime_generation`
- `lifecycle_status`
- `last_heartbeat_at`
- `last_restart_requested_at`
- `last_restart_completed_at`
- `last_error_at`
- `current_worker_shard`
- `version`

### `restart_events`

- `id`
- `company_id`
- `store_id`
- `requested_by_platform_user_id`
- `requested_reason`
- `requested_at`
- `approved_at`
- `started_at`
- `completed_at`
- `status`
- `before_generation`
- `after_generation`

## Observacoes de multi-tenancy

- `platform_users` sao globais
- usuarios do cliente sao memberships em empresa e loja
- `company_id` nunca deve ser inferido apenas pelo frontend
- consultas do tenant devem usar contexto assinado do token + RLS
