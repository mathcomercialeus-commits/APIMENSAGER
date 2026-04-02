from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def record_audit_log(
    session: AsyncSession,
    *,
    action: str,
    resource_type: str,
    actor_user_id: UUID | None = None,
    resource_id: str = "",
    company_id: UUID | None = None,
    store_id: UUID | None = None,
    ip_address: str = "",
    user_agent: str = "",
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        company_id=company_id,
        store_id=store_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata_json=metadata or {},
    )
    session.add(entry)
    await session.flush()
    return entry
