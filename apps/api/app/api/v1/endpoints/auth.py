from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor, get_current_user, request_ip
from app.core.config import settings
from app.core.database import get_db_session
from app.core.security import create_access_token, create_refresh_token, decode_token, verify_password
from app.models.platform import PlatformUser, RefreshToken
from app.schemas.auth import CurrentUserRead, LoginRequest, RefreshRequest, TokenResponse
from app.schemas.user import CompanyMembershipRead, SimpleRoleGrantRead, StoreMembershipRead
from app.services.access import CurrentActor, build_current_actor
from app.services.audit import record_audit_log


router = APIRouter()


def _serialize_role_grant(grant) -> SimpleRoleGrantRead:
    return SimpleRoleGrantRead(
        role_id=grant.role_id,
        role_code=grant.role_code,
        role_name=grant.role_name,
        scope_level=grant.scope_level,
        permissions=sorted(grant.permissions),
    )


def _serialize_actor(actor: CurrentActor) -> CurrentUserRead:
    return CurrentUserRead(
        id=actor.user.id,
        full_name=actor.user.full_name,
        login=actor.user.login,
        email=actor.user.email,
        status=actor.user.status.value,
        permissions=sorted(actor.effective_permissions),
        platform_roles=[_serialize_role_grant(item) for item in actor.platform_roles],
        company_memberships=[
            CompanyMembershipRead(
                company_id=membership.company_id,
                company_name=membership.company.display_name,
                role=_serialize_role_grant(actor.company_roles[membership.company_id]),
                is_active=membership.is_active,
            )
            for membership in actor.user.company_memberships
            if membership.is_active
        ],
        store_memberships=[
            StoreMembershipRead(
                store_id=membership.store_id,
                store_name=membership.store.name,
                company_id=membership.store.company_id,
                company_name=membership.store.company.display_name,
                role=_serialize_role_grant(actor.store_roles[membership.store_id]),
                is_active=membership.is_active,
            )
            for membership in actor.user.store_memberships
            if membership.is_active
        ],
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    user = await session.scalar(
        select(PlatformUser).where(
            or_(PlatformUser.login == payload.login, PlatformUser.email == payload.login)
        )
    )
    now = datetime.now(timezone.utc)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais invalidas.")
    if user.locked_until and user.locked_until > now:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="Usuario temporariamente bloqueado.")
    if not verify_password(payload.password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 5:
            user.locked_until = now + timedelta(minutes=15)
        await record_audit_log(
            session,
            action="auth.login_failed",
            resource_type="platform_user",
            actor_user_id=user.id,
            resource_id=str(user.id),
            ip_address=request_ip(request),
            user_agent=request.headers.get("user-agent", ""),
            metadata={"login": payload.login},
        )
        await session.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais invalidas.")

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    user.last_login_ip = request_ip(request)
    user.last_user_agent = request.headers.get("user-agent", "")

    access_token, expires_in = create_access_token(str(user.id))
    refresh_token, token_jti, _ = create_refresh_token(str(user.id))
    session.add(
        RefreshToken(
            user_id=user.id,
            token_jti=token_jti,
            expires_at=now + timedelta(days=settings.refresh_token_expire_days),
            created_by_ip=request_ip(request),
            user_agent=request.headers.get("user-agent", ""),
        )
    )
    await record_audit_log(
        session,
        action="auth.login_succeeded",
        resource_type="platform_user",
        actor_user_id=user.id,
        resource_id=str(user.id),
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
    )
    await session.commit()

    actor = await build_current_actor(session, user.id)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        user=_serialize_actor(actor),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    payload: RefreshRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    try:
        claims = decode_token(payload.refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    if claims.get("typ") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token invalido.")

    token_jti = claims.get("jti")
    subject = claims.get("sub")
    refresh_row = await session.scalar(select(RefreshToken).where(RefreshToken.token_jti == token_jti))
    if not refresh_row or refresh_row.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revogado.")

    user = await session.get(PlatformUser, UUID(subject))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario nao encontrado.")

    refresh_row.revoked_at = datetime.now(timezone.utc)

    access_token, expires_in = create_access_token(str(user.id))
    new_refresh_token, new_jti, _ = create_refresh_token(str(user.id))
    session.add(
        RefreshToken(
            user_id=user.id,
            token_jti=new_jti,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
            created_by_ip=request_ip(request),
            user_agent=request.headers.get("user-agent", ""),
        )
    )
    await session.commit()

    actor = await build_current_actor(session, user.id)
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=expires_in,
        user=_serialize_actor(actor),
    )


@router.post("/logout")
async def logout(
    payload: RefreshRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: PlatformUser = Depends(get_current_user),
) -> dict[str, str]:
    try:
        claims = decode_token(payload.refresh_token)
    except ValueError:
        return {"message": "Logout processado."}
    if claims.get("typ") != "refresh":
        return {"message": "Logout processado."}

    token_jti = claims.get("jti")
    refresh_row = await session.scalar(select(RefreshToken).where(RefreshToken.token_jti == token_jti))
    if refresh_row and refresh_row.revoked_at is None:
        refresh_row.revoked_at = datetime.now(timezone.utc)
        await record_audit_log(
            session,
            action="auth.logout",
            resource_type="platform_user",
            actor_user_id=current_user.id,
            resource_id=str(current_user.id),
        )
        await session.commit()
    return {"message": "Logout processado."}


@router.get("/me", response_model=CurrentUserRead)
async def me(actor: CurrentActor = Depends(get_current_actor)) -> CurrentUserRead:
    return _serialize_actor(actor)
