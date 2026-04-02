from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, String, Table, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import PlatformUserStatus, RoleScope


role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", PGUUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "permission_id",
        PGUUID(as_uuid=True),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Permission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    scope_level: Mapped[RoleScope] = mapped_column(Enum(RoleScope, native_enum=False), nullable=False)
    module: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)


class Role(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    scope_level: Mapped[RoleScope] = mapped_column(Enum(RoleScope, native_enum=False), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    permissions = relationship("Permission", secondary=role_permissions, lazy="selectin")


class PlatformUser(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "platform_users"

    full_name: Mapped[str] = mapped_column(String(180), nullable=False)
    login: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[PlatformUserStatus] = mapped_column(
        Enum(PlatformUserStatus, native_enum=False),
        default=PlatformUserStatus.ACTIVE,
        nullable=False,
    )
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_login_attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    platform_roles = relationship(
        "PlatformUserRoleAssignment",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    company_memberships = relationship(
        "CompanyMembership",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    store_memberships = relationship(
        "StoreMembership",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PlatformUserRoleAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "platform_user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id"),)

    user_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("platform_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
    )

    user = relationship("PlatformUser", back_populates="platform_roles", lazy="joined")
    role = relationship("Role", lazy="joined")


class RefreshToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("platform_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_jti: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_ip: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    user_agent: Mapped[str] = mapped_column(Text, default="", nullable=False)

    user = relationship("PlatformUser", lazy="joined")
