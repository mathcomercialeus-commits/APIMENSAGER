from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor, request_ip
from app.core.database import get_db_session
from app.models.tenant import Store
from app.schemas.store import StoreCreate, StoreRead, StoreUpdate
from app.services.access import CurrentActor, get_company_or_404, get_store_or_404
from app.services.audit import record_audit_log


router = APIRouter()


def _serialize_store(store: Store) -> StoreRead:
    return StoreRead(
        id=store.id,
        company_id=store.company_id,
        company_name=store.company.display_name,
        name=store.name,
        code=store.code,
        slug=store.slug,
        timezone=store.timezone,
        status=store.status.value,
        heartbeat_enabled=store.heartbeat_enabled,
        support_notes=store.support_notes,
        created_at=store.created_at,
        updated_at=store.updated_at,
    )


@router.get("", response_model=list[StoreRead])
async def list_stores(
    company_id: UUID | None = Query(default=None),
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> list[StoreRead]:
    stmt = select(Store).order_by(Store.name)
    if company_id:
        stmt = stmt.where(Store.company_id == company_id)
        if not actor.can_access_company(company_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem acesso a esta empresa.")
    elif not actor.is_superadmin:
        company_ids = list(actor.company_roles.keys())
        store_ids = list(actor.store_roles.keys())
        if company_ids and store_ids:
            stmt = stmt.where(or_(Store.company_id.in_(company_ids), Store.id.in_(store_ids)))
        elif company_ids:
            stmt = stmt.where(Store.company_id.in_(company_ids))
        elif store_ids:
            stmt = stmt.where(Store.id.in_(store_ids))
        else:
            return []

    stores = (await session.scalars(stmt)).all()
    return [_serialize_store(item) for item in stores]


@router.post("/company/{company_id}", response_model=StoreRead, status_code=status.HTTP_201_CREATED)
async def create_store(
    company_id: UUID,
    payload: StoreCreate,
    request: Request,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> StoreRead:
    company = await get_company_or_404(session, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa nao encontrada.")
    if not actor.has_permission("stores.manage", company_id=company.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para criar loja.")

    store = Store(company_id=company.id, **payload.model_dump())
    session.add(store)
    await session.flush()
    await record_audit_log(
        session,
        action="stores.created",
        resource_type="store",
        actor_user_id=actor.user.id,
        resource_id=str(store.id),
        company_id=company.id,
        store_id=store.id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
    )
    await session.commit()
    await session.refresh(store)
    return _serialize_store(store)


@router.get("/{store_id}", response_model=StoreRead)
async def get_store(
    store_id: UUID,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> StoreRead:
    store = await get_store_or_404(session, store_id)
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loja nao encontrada.")
    if not (actor.can_access_store(store.id) or actor.can_access_company(store.company_id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem acesso a esta loja.")
    return _serialize_store(store)


@router.patch("/{store_id}", response_model=StoreRead)
async def update_store(
    store_id: UUID,
    payload: StoreUpdate,
    request: Request,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> StoreRead:
    store = await get_store_or_404(session, store_id)
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loja nao encontrada.")
    if not actor.has_permission("stores.manage", company_id=store.company_id, store_id=store.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para alterar a loja.")

    changed_fields = payload.model_dump(exclude_unset=True)
    for field, value in changed_fields.items():
        if value is not None:
            setattr(store, field, value)

    await record_audit_log(
        session,
        action="stores.updated",
        resource_type="store",
        actor_user_id=actor.user.id,
        resource_id=str(store.id),
        company_id=store.company_id,
        store_id=store.id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"fields": sorted(changed_fields.keys())},
    )
    await session.commit()
    await session.refresh(store)
    return _serialize_store(store)
