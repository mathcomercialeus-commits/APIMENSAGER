from datetime import datetime
from uuid import UUID

from app.schemas.common import APIModel


class StoreCreate(APIModel):
    name: str
    code: str
    slug: str
    timezone: str = "America/Manaus"


class StoreUpdate(APIModel):
    name: str | None = None
    timezone: str | None = None
    status: str | None = None
    heartbeat_enabled: bool | None = None
    support_notes: str | None = None


class StoreRead(APIModel):
    id: UUID
    company_id: UUID
    company_name: str
    name: str
    code: str
    slug: str
    timezone: str
    status: str
    heartbeat_enabled: bool
    support_notes: str
    created_at: datetime
    updated_at: datetime
