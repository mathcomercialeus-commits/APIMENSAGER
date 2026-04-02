from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor, request_ip
from app.core.database import get_db_session
from app.models.crm import WhatsAppChannel
from app.models.enums import ChannelStatus
from app.schemas.crm import WhatsAppChannelCreate, WhatsAppChannelRead, WhatsAppChannelUpdate
from app.services.access import CurrentActor, get_company_or_404, get_store_or_404
from app.services.audit import record_audit_log
from app.services.crm import serialize_channel


router = APIRouter()


async def _load_channel(session: AsyncSession, channel_id: UUID) -> WhatsAppChannel | None:
    return await session.scalar(select(WhatsAppChannel).where(WhatsAppChannel.id == channel_id))


@router.get("", response_model=list[WhatsAppChannelRead])
async def list_channels(
    company_id: UUID | None = Query(default=None),
    store_id: UUID | None = Query(default=None),
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> list[WhatsAppChannelRead]:
    stmt = select(WhatsAppChannel).order_by(WhatsAppChannel.name)

    if store_id:
        store = await get_store_or_404(session, store_id)
        if not store:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loja nao encontrada.")
        if not actor.has_permission("channels.view", company_id=store.company_id, store_id=store.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem acesso aos canais da loja.")
        stmt = stmt.where(WhatsAppChannel.store_id == store.id)
    elif company_id:
        company = await get_company_or_404(session, company_id)
        if not company:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa nao encontrada.")
        if actor.is_superadmin or company_id in actor.company_roles:
            stmt = stmt.where(WhatsAppChannel.company_id == company_id)
        elif actor.can_access_company(company_id):
            store_ids = [item for item, mapped_company_id in actor.store_to_company.items() if mapped_company_id == company_id]
            if not store_ids:
                return []
            stmt = stmt.where(
                WhatsAppChannel.company_id == company_id,
                WhatsAppChannel.store_id.in_(store_ids),
            )
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem acesso aos canais da empresa.")
    elif not actor.is_superadmin:
        company_ids = list(actor.company_roles.keys())
        store_ids = list(actor.store_roles.keys())
        if company_ids and store_ids:
            stmt = stmt.where(or_(WhatsAppChannel.company_id.in_(company_ids), WhatsAppChannel.store_id.in_(store_ids)))
        elif company_ids:
            stmt = stmt.where(WhatsAppChannel.company_id.in_(company_ids))
        elif store_ids:
            stmt = stmt.where(WhatsAppChannel.store_id.in_(store_ids))
        else:
            return []

    channels = (await session.scalars(stmt)).all()
    return [serialize_channel(channel) for channel in channels]


@router.post("", response_model=WhatsAppChannelRead, status_code=status.HTTP_201_CREATED)
async def create_channel(
    payload: WhatsAppChannelCreate,
    request: Request,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> WhatsAppChannelRead:
    company = await get_company_or_404(session, payload.company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa nao encontrada.")

    store = await get_store_or_404(session, payload.store_id)
    if not store or store.company_id != company.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Loja invalida para esta empresa.")
    if not actor.has_permission("channels.manage", company_id=company.id, store_id=store.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para criar canais.")

    if payload.is_default:
        existing_defaults = (
            await session.scalars(
                select(WhatsAppChannel).where(
                    WhatsAppChannel.company_id == company.id,
                    WhatsAppChannel.store_id == store.id,
                    WhatsAppChannel.is_default.is_(True),
                )
            )
        ).all()
        for channel in existing_defaults:
            channel.is_default = False

    channel = WhatsAppChannel(**payload.model_dump())
    channel.company = company
    channel.store = store
    session.add(channel)
    await session.flush()
    await record_audit_log(
        session,
        action="channels.created",
        resource_type="whatsapp_channel",
        actor_user_id=actor.user.id,
        resource_id=str(channel.id),
        company_id=company.id,
        store_id=store.id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
    )
    await session.commit()
    await session.refresh(channel)
    return serialize_channel(channel)


@router.get("/{channel_id}", response_model=WhatsAppChannelRead)
async def get_channel(
    channel_id: UUID,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> WhatsAppChannelRead:
    channel = await _load_channel(session, channel_id)
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Canal nao encontrado.")
    if not actor.has_permission("channels.view", company_id=channel.company_id, store_id=channel.store_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem acesso a este canal.")
    return serialize_channel(channel)


@router.patch("/{channel_id}", response_model=WhatsAppChannelRead)
async def update_channel(
    channel_id: UUID,
    payload: WhatsAppChannelUpdate,
    request: Request,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> WhatsAppChannelRead:
    channel = await _load_channel(session, channel_id)
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Canal nao encontrado.")
    if not actor.has_permission("channels.manage", company_id=channel.company_id, store_id=channel.store_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para alterar o canal.")

    changed_fields = payload.model_dump(exclude_unset=True)
    status_value = changed_fields.pop("status", None)
    if status_value is not None:
        try:
            channel.status = ChannelStatus(status_value)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Status do canal invalido.") from exc

    if changed_fields.get("is_default") is True:
        existing_defaults = (
            await session.scalars(
                select(WhatsAppChannel).where(
                    WhatsAppChannel.company_id == channel.company_id,
                    WhatsAppChannel.store_id == channel.store_id,
                    WhatsAppChannel.id != channel.id,
                    WhatsAppChannel.is_default.is_(True),
                )
            )
        ).all()
        for current in existing_defaults:
            current.is_default = False

    nullable_fields = {"external_phone_number_id"}
    for field, value in changed_fields.items():
        if value is None and field not in nullable_fields:
            continue
        setattr(channel, field, value)

    await record_audit_log(
        session,
        action="channels.updated",
        resource_type="whatsapp_channel",
        actor_user_id=actor.user.id,
        resource_id=str(channel.id),
        company_id=channel.company_id,
        store_id=channel.store_id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"fields": sorted(payload.model_dump(exclude_unset=True).keys())},
    )
    await session.commit()
    await session.refresh(channel)
    return serialize_channel(channel)
