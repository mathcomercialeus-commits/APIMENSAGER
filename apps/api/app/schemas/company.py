from datetime import datetime
from uuid import UUID

from pydantic import EmailStr

from app.schemas.common import APIModel


class CompanyCreate(APIModel):
    legal_name: str
    display_name: str
    slug: str
    document_number: str | None = None
    billing_email: EmailStr | None = None


class CompanyUpdate(APIModel):
    legal_name: str | None = None
    display_name: str | None = None
    status: str | None = None
    billing_email: EmailStr | None = None


class CompanyRead(APIModel):
    id: UUID
    legal_name: str
    display_name: str
    slug: str
    document_number: str | None
    billing_email: str | None
    status: str
    trial_ends_at: datetime | None
    grace_ends_at: datetime | None
    suspended_at: datetime | None
    created_at: datetime
    updated_at: datetime
