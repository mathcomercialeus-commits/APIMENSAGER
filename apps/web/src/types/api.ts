export type UUID = string;

export interface MessageResponse {
  message: string;
}

export interface PermissionRead {
  id: UUID;
  code: string;
  name: string;
  scope_level: string;
  module: string;
  description: string;
}

export interface RoleRead {
  id: UUID;
  code: string;
  name: string;
  scope_level: string;
  description: string;
  is_system: boolean;
  permissions: PermissionRead[];
  created_at: string;
  updated_at: string;
}

export interface SimpleRoleGrantRead {
  role_id: UUID;
  role_code: string;
  role_name: string;
  scope_level: string;
  permissions: string[];
}

export interface CompanyMembershipRead {
  company_id: UUID;
  company_name: string;
  role: SimpleRoleGrantRead;
  is_active: boolean;
}

export interface StoreMembershipRead {
  store_id: UUID;
  store_name: string;
  company_id: UUID;
  company_name: string;
  role: SimpleRoleGrantRead;
  is_active: boolean;
}

export interface CurrentUserRead {
  id: UUID;
  full_name: string;
  login: string;
  email: string;
  status: string;
  permissions: string[];
  platform_roles: SimpleRoleGrantRead[];
  company_memberships: CompanyMembershipRead[];
  store_memberships: StoreMembershipRead[];
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: CurrentUserRead;
}

export interface CompanyRead {
  id: UUID;
  legal_name: string;
  display_name: string;
  slug: string;
  document_number: string | null;
  billing_email: string | null;
  status: string;
  trial_ends_at: string | null;
  grace_ends_at: string | null;
  suspended_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface StoreRead {
  id: UUID;
  company_id: UUID;
  company_name: string;
  name: string;
  code: string;
  slug: string;
  timezone: string;
  status: string;
  heartbeat_enabled: boolean;
  support_notes: string;
  created_at: string;
  updated_at: string;
}

export interface PlatformUserRead {
  id: UUID;
  full_name: string;
  login: string;
  email: string;
  status: string;
  must_change_password: boolean;
  created_at: string;
  updated_at: string;
  platform_roles: SimpleRoleGrantRead[];
  company_memberships: CompanyMembershipRead[];
  store_memberships: StoreMembershipRead[];
}

export interface BillingPlanRead {
  id: UUID;
  code: string;
  name: string;
  description: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface BillingPlanVersionRead {
  id: UUID;
  plan_id: UUID;
  version_number: number;
  billing_scope: string;
  billing_cycle: string;
  base_amount: number;
  store_amount: number;
  user_amount: number;
  channel_amount: number;
  included_stores: number;
  included_users: number;
  included_channels: number;
  trial_days: number;
  is_current: boolean;
  created_at: string;
  updated_at: string;
}

export interface BillingCustomerRead {
  id: UUID;
  company_id: UUID;
  provider: string;
  provider_customer_id: string;
  name_snapshot: string;
  email_snapshot: string | null;
  document_number_snapshot: string | null;
  created_at: string;
  updated_at: string;
}

export interface SubscriptionRead {
  id: UUID;
  company_id: UUID;
  store_id: UUID | null;
  customer_id: UUID;
  plan_version_id: UUID;
  provider: string;
  provider_subscription_id: string | null;
  scope: string;
  status: string;
  billing_cycle: string;
  price_amount: number;
  current_period_start: string | null;
  current_period_end: string | null;
  next_due_date: string | null;
  trial_ends_at: string | null;
  canceled_at: string | null;
  suspended_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface InvoiceRead {
  id: UUID;
  company_id: UUID;
  store_id: UUID | null;
  subscription_id: UUID | null;
  provider: string;
  provider_invoice_id: string | null;
  status: string;
  amount: number;
  due_date: string | null;
  paid_at: string | null;
  description: string;
  invoice_url: string | null;
  bank_slip_url: string | null;
  pix_qr_code_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaymentRead {
  id: UUID;
  invoice_id: UUID;
  provider: string;
  provider_payment_id: string | null;
  method: string | null;
  status: string;
  amount: number;
  paid_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CompanyBillingSummary {
  company_id: UUID;
  subscription: SubscriptionRead | null;
  open_invoices: InvoiceRead[];
  recent_payments: PaymentRead[];
}

export interface TagRead {
  id: UUID;
  company_id: UUID;
  store_id: UUID | null;
  name: string;
  color_hex: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface WhatsAppChannelRead {
  id: UUID;
  company_id: UUID;
  company_name: string;
  store_id: UUID;
  store_name: string;
  name: string;
  code: string;
  provider: string;
  status: string;
  display_phone_number: string;
  phone_number_e164: string;
  external_phone_number_id: string | null;
  description: string;
  color_hex: string;
  is_default: boolean;
  support_notes: string;
  created_at: string;
  updated_at: string;
}

export interface ContactRead {
  id: UUID;
  company_id: UUID;
  primary_store_id: UUID | null;
  primary_store_name: string | null;
  full_name: string;
  phone_number_e164: string;
  alternate_phone: string | null;
  email: string | null;
  document_number: string | null;
  source: string;
  notes: string;
  status: string;
  last_interaction_at: string | null;
  tags: TagRead[];
  created_at: string;
  updated_at: string;
}

export interface UserCompactRead {
  id: UUID;
  full_name: string;
  login: string;
}

export interface ConversationMessageRead {
  id: UUID;
  conversation_id: UUID;
  author_user: UserCompactRead | null;
  direction: string;
  sender_type: string;
  message_type: string;
  delivery_status: string;
  provider_message_id: string | null;
  text_body: string;
  is_human: boolean;
  sent_at: string;
  delivered_at: string | null;
  read_at: string | null;
  failed_at: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ConversationEventRead {
  id: UUID;
  conversation_id: UUID;
  actor_user: UserCompactRead | null;
  event_type: string;
  description: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ConversationAssignmentRead {
  id: UUID;
  conversation_id: UUID;
  assigned_user: UserCompactRead;
  assigned_by_user: UserCompactRead | null;
  reason: string;
  assigned_at: string;
  released_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationSummaryRead {
  id: UUID;
  company_id: UUID;
  company_name: string;
  store_id: UUID;
  store_name: string;
  channel: WhatsAppChannelRead;
  contact_id: UUID;
  contact_name: string;
  contact_phone_number_e164: string;
  assigned_user: UserCompactRead | null;
  status: string;
  priority: string;
  source: string;
  subject: string;
  funnel_stage: string;
  opened_at: string;
  first_customer_message_at: string | null;
  last_customer_message_at: string | null;
  first_human_response_at: string | null;
  last_message_at: string | null;
  closed_at: string | null;
  closure_reason: string;
  resolution_notes: string;
  first_response_seconds: number | null;
  active_duration_seconds: number | null;
  resolution_seconds: number | null;
  tags: TagRead[];
  created_at: string;
  updated_at: string;
}

export interface ConversationRead extends ConversationSummaryRead {
  contact: ContactRead;
  messages: ConversationMessageRead[];
  events: ConversationEventRead[];
  assignments: ConversationAssignmentRead[];
}

export interface ChannelCredentialRead {
  id: UUID;
  channel_id: UUID;
  phone_number_id: string;
  app_id: string;
  business_account_id: string;
  graph_api_version: string;
  webhook_callback_url: string;
  verify_token_hint: string;
  access_token_last4: string;
  has_access_token: boolean;
  has_app_secret: boolean;
  has_webhook_verify_token: boolean;
  is_active: boolean;
  status_payload: Record<string, unknown>;
  last_healthcheck_at: string | null;
  last_error_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface MessageTemplateRead {
  id: UUID;
  meta_template_id: string;
  name: string;
  language_code: string;
  category: string;
  status: string;
  components_schema: Record<string, unknown>;
  last_synced_at: string | null;
}

export interface TemplatesSyncResponse {
  synced_count: number;
  templates: MessageTemplateRead[];
}

export interface OutboundMessageResponse {
  conversation_id: UUID;
  conversation_message_id: UUID;
  channel_id: UUID;
  provider_message_id: string | null;
  delivery_status: string;
  inside_customer_service_window: boolean;
  provider_response: Record<string, unknown>;
  sent_at: string;
}

export interface RuntimeStateRead {
  id: UUID;
  company_id: UUID;
  store_id: UUID;
  runtime_generation: number;
  lifecycle_status: string;
  heartbeat_interval_seconds: number;
  last_heartbeat_at: string | null;
  queue_depth: number;
  active_jobs: number;
  backlog_count: number;
  current_worker_shard: string;
  version: string;
  last_restart_requested_at: string | null;
  last_restart_started_at: string | null;
  last_restart_completed_at: string | null;
  last_error_at: string | null;
  last_error_message: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface StoreHealthCheckRead {
  id: UUID;
  company_id: UUID;
  store_id: UUID;
  runtime_state_id: UUID | null;
  lifecycle_status: string;
  runtime_generation: number;
  queue_depth: number;
  active_jobs: number;
  backlog_count: number;
  cpu_percent: number | null;
  memory_percent: number | null;
  observed_at: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface IncidentRead {
  id: UUID;
  company_id: UUID;
  store_id: UUID;
  severity: string;
  source: string;
  title: string;
  message: string;
  is_resolved: boolean;
  resolved_at: string | null;
  resolved_by_user_id: UUID | null;
  occurred_at: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface RestartEventRead {
  id: UUID;
  company_id: UUID;
  store_id: UUID;
  requested_by_user_id: UUID | null;
  status: string;
  reason: string;
  requested_at: string;
  started_at: string | null;
  completed_at: string | null;
  failure_message: string;
  before_generation: number;
  after_generation: number;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface AuditLogRead {
  id: UUID;
  actor_user_id: UUID | null;
  action: string;
  resource_type: string;
  resource_id: string;
  company_id: UUID | null;
  store_id: UUID | null;
  ip_address: string;
  user_agent: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface MetaWebhookQueueEventRead {
  id: UUID;
  channel_id: UUID | null;
  company_id: UUID | null;
  store_id: UUID | null;
  phone_number_id: string;
  processing_status: string;
  processing_notes: string;
  processing_attempts: number;
  last_attempt_at: string | null;
  next_retry_at: string | null;
  dead_lettered_at: string | null;
  processed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface MetaWebhookQueuePageRead {
  items: MetaWebhookQueueEventRead[];
  total: number;
  limit: number;
  offset: number;
  order_by: string;
  order_direction: string;
}

export interface BillingProviderEventRead {
  id: UUID;
  company_id: UUID | null;
  subscription_id: UUID | null;
  invoice_id: UUID | null;
  provider_event_id: string | null;
  event_type: string;
  processing_status: string;
  processing_notes: string;
  processing_attempts: number;
  last_attempt_at: string | null;
  next_retry_at: string | null;
  dead_lettered_at: string | null;
  processed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface BillingProviderEventPageRead {
  items: BillingProviderEventRead[];
  total: number;
  limit: number;
  offset: number;
  order_by: string;
  order_direction: string;
}

export interface AutomationExecutionQueueRead {
  id: UUID;
  rule_id: UUID;
  rule_name: string;
  company_id: UUID;
  store_id: UUID;
  channel_id: UUID | null;
  conversation_id: UUID | null;
  requested_by_user_id: UUID | null;
  requested_by_user_name: string | null;
  status: string;
  rendered_message: string;
  result_notes: string;
  provider_message_id: string;
  metadata: Record<string, unknown>;
  processing_attempts: number;
  last_attempt_at: string | null;
  next_retry_at: string | null;
  dead_lettered_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AutomationExecutionQueuePageRead {
  items: AutomationExecutionQueueRead[];
  total: number;
  limit: number;
  offset: number;
  order_by: string;
  order_direction: string;
}

export interface AutomationRuleRead {
  id: UUID;
  company_id: UUID;
  company_name: string;
  store_id: UUID;
  store_name: string;
  channel_id: UUID | null;
  channel_name: string | null;
  name: string;
  description: string;
  trigger_type: string;
  action_type: string;
  is_active: boolean;
  priority: number;
  respect_customer_window: boolean;
  message_body: string;
  template_name: string;
  template_language_code: string;
  settings: Record<string, unknown>;
  last_executed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AutomationExecutionRead {
  id: UUID;
  rule_id: UUID;
  company_id: UUID;
  store_id: UUID;
  channel_id: UUID | null;
  conversation_id: UUID | null;
  requested_by_user_id: UUID | null;
  requested_by_user_name: string | null;
  status: string;
  rendered_message: string;
  result_notes: string;
  provider_message_id: string;
  provider_response: Record<string, unknown>;
  metadata: Record<string, unknown>;
  processing_attempts: number;
  last_attempt_at: string | null;
  next_retry_at: string | null;
  dead_lettered_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface StoreHealthSummary {
  store_id: UUID;
  store_name: string;
  company_id: UUID;
  company_name: string;
  store_status: string;
  effective_status: string;
  runtime_generation: number;
  heartbeat_age_seconds: number | null;
  last_heartbeat_at: string | null;
  last_valid_event_at: string | null;
  active_channels: number;
  degraded_channels: number;
  failed_webhooks_24h: number;
  failed_messages_24h: number;
  unresolved_incidents: number;
  pending_restarts: number;
  queue_depth: number;
  active_jobs: number;
  backlog_count: number;
  version: string;
  last_error_at: string | null;
  last_error_message: string;
}

export interface StoreHealthDetail extends StoreHealthSummary {
  runtime_state: RuntimeStateRead | null;
  recent_health_checks: StoreHealthCheckRead[];
  recent_incidents: IncidentRead[];
  recent_restarts: RestartEventRead[];
}

export interface StatusOverview {
  total_companies: number;
  total_stores: number;
  online_stores: number;
  degraded_stores: number;
  offline_stores: number;
  restarting_stores: number;
  suspended_stores: number;
  failed_webhooks_24h: number;
  failed_messages_24h: number;
  unresolved_incidents: number;
  pending_restarts: number;
  queued_meta_webhooks: number;
  processing_meta_webhooks: number;
  retry_scheduled_meta_webhooks: number;
  dead_lettered_meta_webhooks: number;
  failed_meta_webhooks_total: number;
  queued_billing_events: number;
  processing_billing_events: number;
  retry_scheduled_billing_events: number;
  dead_lettered_billing_events: number;
  failed_billing_events_total: number;
  queued_automation_executions: number;
  processing_automation_executions: number;
  retry_scheduled_automation_executions: number;
  dead_lettered_automation_executions: number;
  failed_automation_executions_total: number;
  skipped_automation_executions: number;
}
