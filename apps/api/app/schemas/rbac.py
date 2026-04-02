from datetime import datetime
from uuid import UUID

from app.schemas.common import APIModel


class PermissionRead(APIModel):
    id: UUID
    code: str
    name: str
    scope_level: str
    module: str
    description: str


class RoleRead(APIModel):
    id: UUID
    code: str
    name: str
    scope_level: str
    description: str
    is_system: bool
    permissions: list[PermissionRead]
    created_at: datetime
    updated_at: datetime
