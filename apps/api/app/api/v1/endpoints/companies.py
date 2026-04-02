from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor, request_ip
from app.core.database import get_db_session
from app.models.tenant import ClientCompany
from app.schemas.company import CompanyCreate, CompanyRead, CompanyUpdate
from app.services.access import CurrentActor, get_company_or_404
from app.services.audit import record_audit_log


router = APIRouter()


def _serialize_company(company: ClientCompany) -> CompanyRead:
    return CompanyRead(
        id=company.id,
        legal_name=company.legal_name,
        display_name=company.display_name,
        slug=company.slug,
        document_number=company.document_number,
        billing_email=company.billing_email,
        status=company.status.value,
        trial_ends_at=company.trial_ends_at,
        grace_ends_at=company.grace_ends_at,
        suspended_at=company.suspended_at,
        created_at=company.created_at,
        updated_at=company.updated_at,
    )


@router.get("", response_model=list[CompanyRead])
async def list_companies(
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> list[CompanyRead]:
    if actor.is_superadmin:
        companies = (await session.scalars(select(ClientCompany).order_by(ClientCompany.display_name))).all()
    else:
        company_ids = list({*actor.company_roles.keys(), *actor.store_to_company.values()})
        if not company_ids:
            return []
        companies = (
            await session.scalars(
                select(ClientCompany)
                .where(ClientCompany.id.in_(company_ids))
                .order_by(ClientCompany.display_name)
            )
        ).all()
    return [_serialize_company(item) for item in companies]


@router.post("", response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
async def create_company(
    payload: CompanyCreate,
    request: Request,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> CompanyRead:
    if not actor.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Apenas superadmin cria empresas.")

    company = ClientCompany(**payload.model_dump())
    session.add(company)
    await session.flush()
    await record_audit_log(
        session,
        action="companies.created",
        resource_type="client_company",
        actor_user_id=actor.user.id,
        resource_id=str(company.id),
        company_id=company.id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
    )
    await session.commit()
    await session.refresh(company)
    return _serialize_company(company)


@router.get("/{company_id}", response_model=CompanyRead)
async def get_company(
    company_id: UUID,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> CompanyRead:
    company = await get_company_or_404(session, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa nao encontrada.")
    if not actor.can_access_company(company.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem acesso a esta empresa.")
    return _serialize_company(company)


@router.patch("/{company_id}", response_model=CompanyRead)
async def update_company(
    company_id: UUID,
    payload: CompanyUpdate,
    request: Request,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_db_session),
) -> CompanyRead:
    company = await get_company_or_404(session, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa nao encontrada.")
    if not actor.has_permission("companies.manage", company_id=company.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para alterar a empresa.")

    changed_fields = payload.model_dump(exclude_unset=True)
    for field, value in changed_fields.items():
        if value is not None:
            setattr(company, field, value)

    await record_audit_log(
        session,
        action="companies.updated",
        resource_type="client_company",
        actor_user_id=actor.user.id,
        resource_id=str(company.id),
        company_id=company.id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"fields": sorted(changed_fields.keys())},
    )
    await session.commit()
    await session.refresh(company)
    return _serialize_company(company)
