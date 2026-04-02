from enum import StrEnum


class PlatformUserStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"


class RoleScope(StrEnum):
    PLATFORM = "platform"
    COMPANY = "company"
    STORE = "store"


class CompanyStatus(StrEnum):
    TRIAL = "trial"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    SUSPENDED = "suspended"
    BLOCKED = "blocked"


class StoreStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class ChannelProvider(StrEnum):
    META_CLOUD_API = "meta_cloud_api"


class ChannelStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class ContactStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"


class ConversationStatus(StrEnum):
    NEW = "new"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    AWAITING_CUSTOMER = "awaiting_customer"
    AWAITING_INTERNAL = "awaiting_internal"
    CLOSED = "closed"
    LOST = "lost"
    CANCELED = "canceled"


class ConversationPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class MessageDirection(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageSenderType(StrEnum):
    CUSTOMER = "customer"
    AGENT = "agent"
    BOT = "bot"
    SYSTEM = "system"


class MessageType(StrEnum):
    TEXT = "text"
    TEMPLATE = "template"
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"
    VIDEO = "video"
    INTERACTIVE = "interactive"
    SYSTEM = "system"


class MessageDeliveryStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class ConversationEventType(StrEnum):
    OPENED = "opened"
    STATUS_CHANGED = "status_changed"
    ASSIGNED = "assigned"
    UNASSIGNED = "unassigned"
    MESSAGE_LOGGED = "message_logged"
    NOTE_ADDED = "note_added"
    TAG_ATTACHED = "tag_attached"
    TAG_REMOVED = "tag_removed"
    UPDATED = "updated"


class RuntimeLifecycleStatus(StrEnum):
    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    RESTARTING = "restarting"
    SUSPENDED = "suspended"


class RestartEventStatus(StrEnum):
    REQUESTED = "requested"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class IncidentSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class BillingProvider(StrEnum):
    ASAAS = "asaas"


class BillingScope(StrEnum):
    COMPANY = "company"
    STORE = "store"


class BillingCycle(StrEnum):
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMIANNUALLY = "semiannually"
    YEARLY = "yearly"


class SubscriptionStatus(StrEnum):
    DRAFT = "draft"
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    SUSPENDED = "suspended"
    CANCELED = "canceled"


class InvoiceStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELED = "canceled"
    REFUNDED = "refunded"
    FAILED = "failed"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    RECEIVED = "received"
    OVERDUE = "overdue"
    REFUNDED = "refunded"
    FAILED = "failed"


class PaymentMethod(StrEnum):
    BOLETO = "boleto"
    PIX = "pix"
    CREDIT_CARD = "credit_card"


class AutomationTriggerType(StrEnum):
    MANUAL = "manual"
    CONVERSATION_OPENED = "conversation_opened"
    CONVERSATION_ASSIGNED = "conversation_assigned"
    OUT_OF_HOURS = "out_of_hours"


class AutomationActionType(StrEnum):
    SEND_TEXT = "send_text"
    SEND_TEMPLATE = "send_template"
    CLOSE_CONVERSATION = "close_conversation"


class AutomationExecutionStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    EXECUTED = "executed"
    SKIPPED = "skipped"
    FAILED = "failed"
