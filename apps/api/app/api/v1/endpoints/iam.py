from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor, require_superadmin, request_ip
from app.core.database import get_db_session
from app.core.security import hash_password
from app.models.platform import Permission, PlatformUser, PlatformUserRoleAssignment, Role
from app.models.tenant import CompanyMembership, StoreMembership
from app.schemas.rbac import PermissionRead, RoleRead
from app.schemas.user import (
    CompanyMembershipCreate,
    CompanyMembershipRead,
    PlatformRoleGrantCreate,
    PlatformUserCreate,
    PlatformUserRead,
    SimpleRoleGrantRead,
    StoreMembershipCreate,
    StoreMembershipRead,
)
from app.services.access import CurrentActor, get_company_or_404, get_role_by_code, get_store_or_404, user_access_options
from app.services.audit import record_audit_log


router = APIRouter()


def _role_to_schema(role: Role) -> RoleRead:
    return RoleRead(
        id=role.id,
        code=role.code,
        name=role.name,
        scope_level=role.scope_level.value,
        description=role.description,
        is_system=role.is_system,
        permissions=[
            PermissionRead(
                id=permission.id,
                code=permission.code,
                name=permission.name,
                scope_level=permission.scope_level.value,
                module=permission.module,
                description=permission.description,
            )
            for permission in role.permissions
        ],
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


def _grant_schema(role: Role) -> SimpleRoleGrantRead:
    return SimpleRoleGrantRead(
        role_id=role.id,
        role_code=role.code,
        role_name=role.name,
        scope_level=role.scope_level.value,
        permissions=sorted(permission.code for permission in role.permissions),
    )


def _user_schema(user: PlatformUser) -> PlatformUserRead:
    return PlatformUserRead(
        id=user.id,
        full_name=user.full_name,
        login=user.login,
        email=user.email,
        status=user.status.value,
        must_change_password=user.must_change_password,
        created_at=user.created_at,
        updated_at=user.updated_at,
        platform_roles=[_grant_schema(item.role) for item in user.platform_roles],
        company_memberships=[
            CompanyMembershipRead(
                company_id=item.company_id,
                company_name=item.company.display_name,
                role=_grant_schema(item.role),
                is_active=item.is_active,
            )
            for item in user.company_memberships
        ],
        store_memberships=[
            StoreMembershipRead(
                store_id=item.store_id,
                store_name=item.store.name,
                company_id=item.store.company_id,
                company_name=item.store.company.display_name,
                role=_grant_schema(item.role),
                is_active=item.is_active,
            )
            for item in user.store_memberships
        ],
    )


@router.get("/permissions", response_model=list[PermissionRead])
async def list_permissions(
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> list[PermissionRead]:
    permissions = (await session.scalars(select(Permission).order_by(Permission.scope_level, Permission.code))).all()
    if not actor.is_superadmin:
        permissions = [item for item in permissions if item.scope_level.value != "platform"]
    return [
        PermissionRead(
            id=item.id,
            code=item.code,
            name=item.name,
            scope_level=item.scope_level.value,
            module=item.module,
            description=item.description,
        )
        for item in permissions
    ]


@router.get("/roles", response_model=list[RoleRead])
async def list_roles(
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> list[RoleRead]:
    roles = (await session.scalars(select(Role).order_by(Role.scope_level, Role.code))).all()
    if not actor.is_superadmin:
        roles = [item for item in roles if item.scope_level.value != "platform"]
    return [_role_to_schema(role) for role in roles]


@router.get("/users", response_model=list[PlatformUserRead])
async def list_users(
    company_id: UUID | None = Query(default=None),
    store_id: UUID | None = Query(default=None),
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> list[PlatformUserRead]:
    stmt = select(PlatformUser).options(*user_access_options()).order_by(PlatformUser.full_name)
    if store_id:
        store = await get_store_or_404(session, store_id)
        if not store:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loja nao encontrada.")
        if not actor.has_permission("users.view", company_id=store.company_id, store_id=store.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para ver usuarios.")
        stmt = stmt.join(StoreMembership).where(StoreMembership.store_id == store_id)
    elif company_id:
        company = await get_company_or_404(session, company_id)
        if not company:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa nao encontrada.")
        if not actor.has_permission("users.view", company_id=company.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para ver usuarios.")
        stmt = stmt.join(CompanyMembership).where(CompanyMembership.company_id == company_id)
    elif not actor.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe company_id ou store_id para listar usuarios neste escopo.",
        )
    users = (await session.scalars(stmt)).unique().all()
    return [_user_schema(user) for user in users]


@router.post("/users", response_model=PlatformUserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: PlatformUserCreate,
    request: Request,
    actor: CurrentActor = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db_session),
) -> PlatformUserRead:
    user = PlatformUser(
        full_name=payload.full_name,
        login=payload.login,
        email=str(payload.email),
        password_hash=hash_password(payload.password),
        must_change_password=payload.must_change_password,
    )
    session.add(user)
    await session.flush()
    await record_audit_log(
        session,
        action="users.created",
        resource_type="platform_user",
        actor_user_id=actor.user.id,
        resource_id=str(user.id),
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
    )
    await session.commit()
    result = await session.scalar(select(PlatformUser).where(PlatformUser.id == user.id).options(*user_access_options()))
    return _user_schema(result)


@router.post("/users/{user_id}/platform-roles", response_model=PlatformUserRead)
async def assign_platform_role(
    user_id: UUID,
    payload: PlatformRoleGrantCreate,
    request: Request,
    actor: CurrentActor = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db_session),
) -> PlatformUserRead:
    user = await session.scalar(select(PlatformUser).where(PlatformUser.id == user_id).options(*user_access_options()))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado.")

    role = await get_role_by_code(session, payload.role_code)
    if not role or role.scope_level.value != "platform":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role de plataforma invalido.")

    existing = await session.scalar(
        select(PlatformUserRoleAssignment).where(
            PlatformUserRoleAssignment.user_id == user.id,
            PlatformUserRoleAssignment.role_id == role.id,
        )
    )
    if not existing:
        session.add(PlatformUserRoleAssignment(user_id=user.id, role_id=role.id))
        await record_audit_log(
            session,
            action="users.platform_role_granted",
            resource_type="platform_user",
            actor_user_id=actor.user.id,
            resource_id=str(user.id),
            ip_address=request_ip(request),
            user_agent=request.headers.get("user-agent", ""),
            metadata={"role_code": role.code},
        )
        await session.commit()

    user = await session.scalar(select(PlatformUser).where(PlatformUser.id == user.id).options(*user_access_options()))
    return _user_schema(user)


@router.post("/company-memberships", response_model=PlatformUserRead)
async def grant_company_membership(
    payload: CompanyMembershipCreate,
    request: Request,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> PlatformUserRead:
    company = await get_company_or_404(session, payload.company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa nao encontrada.")
    if not actor.has_permission("users.manage", company_id=company.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para gerenciar usuarios.")

    user = await session.scalar(select(PlatformUser).where(PlatformUser.id == payload.user_id).options(*user_access_options()))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado.")

    role = await get_role_by_code(session, payload.role_code)
    if not role or role.scope_level.value != "company":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role de empresa invalido.")

    membership = await session.scalar(
        select(CompanyMembership).where(
            CompanyMembership.user_id == user.id,
            CompanyMembership.company_id == company.id,
        )
    )
    if membership:
        membership.role_id = role.id
        membership.is_active = True
    else:
        session.add(CompanyMembership(user_id=user.id, company_id=company.id, role_id=role.id))

    await record_audit_log(
        session,
        action="users.company_membership_granted",
        resource_type="company_membership",
        actor_user_id=actor.user.id,
        resource_id=str(user.id),
        company_id=company.id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"role_code": role.code},
    )
    await session.commit()
    user = await session.scalar(select(PlatformUser).where(PlatformUser.id == user.id).options(*user_access_options()))
    return _user_schema(user)


@router.post("/store-memberships", response_model=PlatformUserRead)
async def grant_store_membership(
    payload: StoreMembershipCreate,
    request: Request,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> PlatformUserRead:
    store = await get_store_or_404(session, payload.store_id)
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loja nao encontrada.")
    if not actor.has_permission("users.manage", company_id=store.company_id, store_id=store.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para gerenciar usuarios.")

    user = await session.scalar(select(PlatformUser).where(PlatformUser.id == payload.user_id).options(*user_access_options()))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado.")

    role = await get_role_by_code(session, payload.role_code)
    if not role or role.scope_level.value != "store":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role de loja invalido.")

    membership = await session.scalar(
        select(StoreMembership).where(
            StoreMembership.user_id == user.id,
            StoreMembership.store_id == store.id,
        )
    )
    if membership:
        membership.role_id = role.id
        membership.is_active = True
    else:
        session.add(StoreMembership(user_id=user.id, store_id=store.id, role_id=role.id))

    await record_audit_log(
        session,
        action="users.store_membership_granted",
        resource_type="store_membership",
        actor_user_id=actor.user.id,
        resource_id=str(user.id),
        company_id=store.company_id,
        store_id=store.id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"role_code": role.code},
    )
    await session.commit()
    user = await session.scalar(select(PlatformUser).where(PlatformUser.id == user.id).options(*user_access_options()))
    return _user_schema(user)
