from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import CompanyStatus, StoreStatus


class ClientCompany(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "client_companies"

    legal_name: Mapped[str] = mapped_column(String(180), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    document_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    billing_email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[CompanyStatus] = mapped_column(
        Enum(CompanyStatus, native_enum=False),
        default=CompanyStatus.TRIAL,
        nullable=False,
    )
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    grace_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    stores = relationship("Store", back_populates="company", lazy="selectin")
    memberships = relationship(
        "CompanyMembership",
        back_populates="company",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Store(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stores"
    __table_args__ = (UniqueConstraint("company_id", "code"),)

    company_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("client_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    timezone: Mapped[str] = mapped_column(String(80), default="America/Manaus", nullable=False)
    status: Mapped[StoreStatus] = mapped_column(
        Enum(StoreStatus, native_enum=False),
        default=StoreStatus.ACTIVE,
        nullable=False,
    )
    heartbeat_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    support_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)

    company = relationship("ClientCompany", back_populates="stores", lazy="joined")
    memberships = relationship(
        "StoreMembership",
        back_populates="store",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CompanyMembership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "company_memberships"
    __table_args__ = (UniqueConstraint("user_id", "company_id"),)

    user_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("platform_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("client_companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    role_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("roles.id"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("PlatformUser", back_populates="company_memberships", lazy="joined")
    company = relationship("ClientCompany", back_populates="memberships", lazy="joined")
    role = relationship("Role", lazy="joined")


class StoreMembership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "store_memberships"
    __table_args__ = (UniqueConstraint("user_id", "store_id"),)

    user_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("platform_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    store_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
    )
    role_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("roles.id"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("PlatformUser", back_populates="store_memberships", lazy="joined")
    store = relationship("Store", back_populates="memberships", lazy="joined")
    role = relationship("Role", lazy="joined")
