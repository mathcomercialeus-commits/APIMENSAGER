from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.security import decode_token
from app.models.enums import PlatformUserStatus
from app.models.platform import PlatformUser
from app.services.access import CurrentActor, build_current_actor


bearer_scheme = HTTPBearer(auto_error=False)


def request_ip(request: Request) -> str:
    return request.client.host if request.client else ""


async def get_current_user(
    session: AsyncSession = Depends(get_db_session),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> PlatformUser:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticacao obrigatoria.")

    try:
        payload = decode_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    if payload.get("typ") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de acesso invalido.")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token sem sujeito.")

    user = await session.get(PlatformUser, UUID(user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario nao encontrado.")
    if user.status != PlatformUserStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario inativo ou bloqueado.")
    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="Usuario temporariamente bloqueado.")
    return user


async def get_current_actor(
    session: AsyncSession = Depends(get_db_session),
    current_user: PlatformUser = Depends(get_current_user),
) -> CurrentActor:
    return await build_current_actor(session, current_user.id)


async def require_superadmin(actor: CurrentActor = Depends(get_current_actor)) -> CurrentActor:
    if not actor.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito ao superadmin.")
    return actor
