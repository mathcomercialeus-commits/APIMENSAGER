from datetime import datetime
from uuid import UUID

from pydantic import EmailStr

from app.schemas.common import APIModel


class PlatformUserCreate(APIModel):
    full_name: str
    login: str
    email: EmailStr
    password: str
    must_change_password: bool = False


class PlatformRoleGrantCreate(APIModel):
    role_code: str


class CompanyMembershipCreate(APIModel):
    user_id: UUID
    company_id: UUID
    role_code: str


class StoreMembershipCreate(APIModel):
    user_id: UUID
    store_id: UUID
    role_code: str


class SimpleRoleGrantRead(APIModel):
    role_id: UUID
    role_code: str
    role_name: str
    scope_level: str
    permissions: list[str]


class CompanyMembershipRead(APIModel):
    company_id: UUID
    company_name: str
    role: SimpleRoleGrantRead
    is_active: bool


class StoreMembershipRead(APIModel):
    store_id: UUID
    store_name: str
    company_id: UUID
    company_name: str
    role: SimpleRoleGrantRead
    is_active: bool


class PlatformUserRead(APIModel):
    id: UUID
    full_name: str
    login: str
    email: str
    status: str
    must_change_password: bool
    created_at: datetime
    updated_at: datetime
    platform_roles: list[SimpleRoleGrantRead]
    company_memberships: list[CompanyMembershipRead]
    store_memberships: list[StoreMembershipRead]
