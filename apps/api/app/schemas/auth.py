from uuid import UUID

from app.schemas.common import APIModel
from app.schemas.user import CompanyMembershipRead, SimpleRoleGrantRead, StoreMembershipRead


class LoginRequest(APIModel):
    login: str
    password: str


class RefreshRequest(APIModel):
    refresh_token: str


class CurrentUserRead(APIModel):
    id: UUID
    full_name: str
    login: str
    email: str
    status: str
    permissions: list[str]
    platform_roles: list[SimpleRoleGrantRead]
    company_memberships: list[CompanyMembershipRead]
    store_memberships: list[StoreMembershipRead]


class TokenResponse(APIModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: CurrentUserRead
