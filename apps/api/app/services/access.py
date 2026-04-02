from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.platform import PlatformUser, PlatformUserRoleAssignment, Role
from app.models.tenant import ClientCompany, CompanyMembership, Store, StoreMembership


@dataclass
class RoleGrant:
    role_id: UUID
    role_code: str
    role_name: str
    scope_level: str
    permissions: set[str]


@dataclass
class CurrentActor:
    user: PlatformUser
    platform_roles: list[RoleGrant] = field(default_factory=list)
    company_roles: dict[UUID, RoleGrant] = field(default_factory=dict)
    store_roles: dict[UUID, RoleGrant] = field(default_factory=dict)
    store_to_company: dict[UUID, UUID] = field(default_factory=dict)

    @property
    def effective_permissions(self) -> set[str]:
        permissions = set()
        for grant in self.platform_roles:
            permissions.update(grant.permissions)
        for grant in self.company_roles.values():
            permissions.update(grant.permissions)
        for grant in self.store_roles.values():
            permissions.update(grant.permissions)
        return permissions

    @property
    def is_superadmin(self) -> bool:
        return any(grant.role_code == "platform_superadmin" for grant in self.platform_roles)

    def has_permission(
        self,
        permission_code: str,
        *,
        company_id: UUID | None = None,
        store_id: UUID | None = None,
    ) -> bool:
        if self.is_superadmin:
            return True

        if any(permission_code in grant.permissions for grant in self.platform_roles):
            return True

        if store_id:
            store_grant = self.store_roles.get(store_id)
            if store_grant and permission_code in store_grant.permissions:
                return True
            mapped_company_id = self.store_to_company.get(store_id)
            if mapped_company_id:
                company_grant = self.company_roles.get(mapped_company_id)
                if company_grant and permission_code in company_grant.permissions:
                    return True

        if company_id:
            company_grant = self.company_roles.get(company_id)
            if company_grant and permission_code in company_grant.permissions:
                return True

        return False

    def can_access_company(self, company_id: UUID) -> bool:
        return self.is_superadmin or company_id in self.company_roles or company_id in self.store_to_company.values()

    def can_access_store(self, store_id: UUID) -> bool:
        return self.is_superadmin or store_id in self.store_roles or store_id in self.store_to_company


def _grant_from_role(role: Role) -> RoleGrant:
    return RoleGrant(
        role_id=role.id,
        role_code=role.code,
        role_name=role.name,
        scope_level=role.scope_level.value,
        permissions={permission.code for permission in role.permissions},
    )


def user_access_options():
    return (
        selectinload(PlatformUser.platform_roles)
        .selectinload(PlatformUserRoleAssignment.role)
        .selectinload(Role.permissions),
        selectinload(PlatformUser.company_memberships)
        .selectinload(CompanyMembership.role)
        .selectinload(Role.permissions),
        selectinload(PlatformUser.company_memberships).selectinload(CompanyMembership.company),
        selectinload(PlatformUser.store_memberships)
        .selectinload(StoreMembership.role)
        .selectinload(Role.permissions),
        selectinload(PlatformUser.store_memberships)
        .selectinload(StoreMembership.store)
        .selectinload(Store.company),
    )


async def load_user_with_access(session: AsyncSession, user_id: UUID) -> PlatformUser | None:
    return await session.scalar(
        select(PlatformUser)
        .where(PlatformUser.id == user_id)
        .options(*user_access_options())
    )


async def build_current_actor(session: AsyncSession, user_id: UUID) -> CurrentActor:
    user = await load_user_with_access(session, user_id)
    if not user:
        raise ValueError("Usuario nao encontrado.")

    actor = CurrentActor(user=user)
    actor.platform_roles = [_grant_from_role(item.role) for item in user.platform_roles]
    actor.company_roles = {
        membership.company_id: _grant_from_role(membership.role)
        for membership in user.company_memberships
        if membership.is_active
    }
    actor.store_roles = {
        membership.store_id: _grant_from_role(membership.role)
        for membership in user.store_memberships
        if membership.is_active
    }
    actor.store_to_company = {
        membership.store_id: membership.store.company_id
        for membership in user.store_memberships
        if membership.is_active
    }
    return actor


async def get_role_by_code(session: AsyncSession, role_code: str) -> Role | None:
    return await session.scalar(select(Role).where(Role.code == role_code).options(selectinload(Role.permissions)))


async def get_company_or_404(session: AsyncSession, company_id: UUID) -> ClientCompany | None:
    return await session.scalar(select(ClientCompany).where(ClientCompany.id == company_id))


async def get_store_or_404(session: AsyncSession, store_id: UUID) -> Store | None:
    return await session.scalar(select(Store).where(Store.id == store_id).options(selectinload(Store.company)))
