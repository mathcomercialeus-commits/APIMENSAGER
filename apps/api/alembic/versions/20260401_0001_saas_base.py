"""saas base auth and tenants

Revision ID: 20260401_0001
Revises:
Create Date: 2026-04-01 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260401_0001"
down_revision = None
branch_labels = None
depends_on = None


role_scope = sa.Enum("platform", "company", "store", name="rolescope", native_enum=False)
platform_user_status = sa.Enum("active", "inactive", "blocked", name="platformuserstatus", native_enum=False)
company_status = sa.Enum(
    "trial",
    "active",
    "past_due",
    "suspended",
    "blocked",
    name="companystatus",
    native_enum=False,
)
store_status = sa.Enum("active", "inactive", "suspended", name="storestatus", native_enum=False)


def upgrade() -> None:
    op.create_table(
        "permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("scope_level", role_scope, nullable=False),
        sa.Column("module", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_permissions")),
    )
    op.create_index(op.f("ix_permissions_code"), "permissions", ["code"], unique=True)

    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("scope_level", role_scope, nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
    )
    op.create_index(op.f("ix_roles_code"), "roles", ["code"], unique=True)

    op.create_table(
        "platform_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.String(length=180), nullable=False),
        sa.Column("login", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=160), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("status", platform_user_status, nullable=False, server_default="active"),
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_ip", sa.String(length=64), nullable=True),
        sa.Column("last_user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_platform_users")),
    )
    op.create_index(op.f("ix_platform_users_login"), "platform_users", ["login"], unique=True)
    op.create_index(op.f("ix_platform_users_email"), "platform_users", ["email"], unique=True)

    op.create_table(
        "client_companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("legal_name", sa.String(length=180), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("document_number", sa.String(length=32), nullable=True),
        sa.Column("billing_email", sa.String(length=160), nullable=True),
        sa.Column("status", company_status, nullable=False, server_default="trial"),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grace_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_client_companies")),
    )
    op.create_index(op.f("ix_client_companies_slug"), "client_companies", ["slug"], unique=True)

    op.create_table(
        "stores",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("timezone", sa.String(length=80), nullable=False, server_default="America/Manaus"),
        sa.Column("status", store_status, nullable=False, server_default="active"),
        sa.Column("heartbeat_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("support_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["client_companies.id"], name=op.f("fk_stores_company_id_client_companies"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stores")),
        sa.UniqueConstraint("company_id", "code", name=op.f("uq_stores_company_id")),
    )
    op.create_index(op.f("ix_stores_company_id"), "stores", ["company_id"], unique=False)
    op.create_index(op.f("ix_stores_slug"), "stores", ["slug"], unique=True)

    op.create_table(
        "role_permissions",
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], name=op.f("fk_role_permissions_permission_id_permissions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], name=op.f("fk_role_permissions_role_id_roles"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "permission_id", name=op.f("pk_role_permissions")),
    )

    op.create_table(
        "platform_user_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], name=op.f("fk_platform_user_roles_role_id_roles"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["platform_users.id"], name=op.f("fk_platform_user_roles_user_id_platform_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_platform_user_roles")),
        sa.UniqueConstraint("user_id", "role_id", name=op.f("uq_platform_user_roles_user_id")),
    )

    op.create_table(
        "company_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["client_companies.id"], name=op.f("fk_company_memberships_company_id_client_companies"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], name=op.f("fk_company_memberships_role_id_roles")),
        sa.ForeignKeyConstraint(["user_id"], ["platform_users.id"], name=op.f("fk_company_memberships_user_id_platform_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_company_memberships")),
        sa.UniqueConstraint("user_id", "company_id", name=op.f("uq_company_memberships_user_id")),
    )

    op.create_table(
        "store_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], name=op.f("fk_store_memberships_role_id_roles")),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], name=op.f("fk_store_memberships_store_id_stores"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["platform_users.id"], name=op.f("fk_store_memberships_user_id_platform_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_store_memberships")),
        sa.UniqueConstraint("user_id", "store_id", name=op.f("uq_store_memberships_user_id")),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_jti", sa.String(length=120), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_ip", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("user_agent", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["platform_users.id"], name=op.f("fk_refresh_tokens_user_id_platform_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
    )
    op.create_index(op.f("ix_refresh_tokens_token_jti"), "refresh_tokens", ["token_jti"], unique=True)

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("resource_type", sa.String(length=120), nullable=False),
        sa.Column("resource_id", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("user_agent", sa.Text(), nullable=False, server_default=""),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["platform_users.id"], name=op.f("fk_audit_logs_actor_user_id_platform_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["client_companies.id"], name=op.f("fk_audit_logs_company_id_client_companies"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], name=op.f("fk_audit_logs_store_id_stores"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_logs_action"), table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index(op.f("ix_refresh_tokens_token_jti"), table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_table("store_memberships")
    op.drop_table("company_memberships")
    op.drop_table("platform_user_roles")
    op.drop_table("role_permissions")
    op.drop_index(op.f("ix_stores_slug"), table_name="stores")
    op.drop_index(op.f("ix_stores_company_id"), table_name="stores")
    op.drop_table("stores")
    op.drop_index(op.f("ix_client_companies_slug"), table_name="client_companies")
    op.drop_table("client_companies")
    op.drop_index(op.f("ix_platform_users_email"), table_name="platform_users")
    op.drop_index(op.f("ix_platform_users_login"), table_name="platform_users")
    op.drop_table("platform_users")
    op.drop_index(op.f("ix_roles_code"), table_name="roles")
    op.drop_table("roles")
    op.drop_index(op.f("ix_permissions_code"), table_name="permissions")
    op.drop_table("permissions")
