from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audit_logs"

    actor_user_id: Mapped[PGUUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("platform_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    company_id: Mapped[PGUUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("client_companies.id", ondelete="SET NULL"),
        nullable=True,
    )
    store_id: Mapped[PGUUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="SET NULL"),
        nullable=True,
    )
    ip_address: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    user_agent: Mapped[str] = mapped_column(Text, default="", nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    actor = relationship("PlatformUser", lazy="joined")
