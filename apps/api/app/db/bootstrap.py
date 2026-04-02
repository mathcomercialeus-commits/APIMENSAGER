from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.models.enums import RoleScope
from app.models.platform import Permission, PlatformUser, PlatformUserRoleAssignment, Role


PERMISSIONS: Sequence[dict[str, str]] = (
    {
        "code": "platform.admin",
        "name": "Administracao global da plataforma",
        "scope_level": RoleScope.PLATFORM,
        "module": "platform",
        "description": "Permite operar todo o control plane.",
    },
    {
        "code": "billing.view",
        "name": "Visualizar billing",
        "scope_level": RoleScope.COMPANY,
        "module": "billing",
        "description": "Visualiza assinatura, invoices e pagamentos.",
    },
    {
        "code": "billing.manage",
        "name": "Gerenciar billing",
        "scope_level": RoleScope.COMPANY,
        "module": "billing",
        "description": "Cria planos, subscriptions e aciona cobrancas.",
    },
    {
        "code": "companies.view",
        "name": "Visualizar empresas",
        "scope_level": RoleScope.COMPANY,
        "module": "companies",
        "description": "Visualiza dados da empresa cliente.",
    },
    {
        "code": "companies.manage",
        "name": "Gerenciar empresas",
        "scope_level": RoleScope.COMPANY,
        "module": "companies",
        "description": "Cria e altera empresas cliente.",
    },
    {
        "code": "stores.view",
        "name": "Visualizar lojas",
        "scope_level": RoleScope.STORE,
        "module": "stores",
        "description": "Visualiza lojas e unidades.",
    },
    {
        "code": "stores.manage",
        "name": "Gerenciar lojas",
        "scope_level": RoleScope.COMPANY,
        "module": "stores",
        "description": "Cria e altera lojas da empresa.",
    },
    {
        "code": "channels.view",
        "name": "Visualizar canais WhatsApp",
        "scope_level": RoleScope.STORE,
        "module": "channels",
        "description": "Visualiza canais e numeros WhatsApp da loja.",
    },
    {
        "code": "channels.manage",
        "name": "Gerenciar canais WhatsApp",
        "scope_level": RoleScope.COMPANY,
        "module": "channels",
        "description": "Cria e altera canais WhatsApp por empresa e loja.",
    },
    {
        "code": "meta.view",
        "name": "Visualizar integracao Meta",
        "scope_level": RoleScope.COMPANY,
        "module": "meta",
        "description": "Consulta templates, credenciais mascaradas e saude da integracao oficial.",
    },
    {
        "code": "meta.manage",
        "name": "Gerenciar integracao Meta",
        "scope_level": RoleScope.COMPANY,
        "module": "meta",
        "description": "Atualiza credenciais, webhook e configuracoes da Cloud API.",
    },
    {
        "code": "templates.manage",
        "name": "Gerenciar templates oficiais",
        "scope_level": RoleScope.COMPANY,
        "module": "meta",
        "description": "Sincroniza e consulta templates oficiais da Meta por canal.",
    },
    {
        "code": "automations.view",
        "name": "Visualizar automacoes",
        "scope_level": RoleScope.STORE,
        "module": "automations",
        "description": "Visualiza regras e historico de automacoes oficiais.",
    },
    {
        "code": "automations.manage",
        "name": "Gerenciar automacoes",
        "scope_level": RoleScope.STORE,
        "module": "automations",
        "description": "Cria, altera e executa automacoes no escopo permitido.",
    },
    {
        "code": "ops.view",
        "name": "Visualizar operacao e saude",
        "scope_level": RoleScope.STORE,
        "module": "ops",
        "description": "Visualiza status, incidentes e saude operacional de lojas.",
    },
    {
        "code": "audit.view",
        "name": "Visualizar auditoria",
        "scope_level": RoleScope.COMPANY,
        "module": "audit",
        "description": "Consulta logs de auditoria e acoes criticas no escopo permitido.",
    },
    {
        "code": "users.view",
        "name": "Visualizar usuarios",
        "scope_level": RoleScope.COMPANY,
        "module": "users",
        "description": "Lista usuarios do tenant.",
    },
    {
        "code": "users.manage",
        "name": "Gerenciar usuarios",
        "scope_level": RoleScope.COMPANY,
        "module": "users",
        "description": "Concede memberships e papeis.",
    },
    {
        "code": "contacts.view",
        "name": "Visualizar contatos",
        "scope_level": RoleScope.STORE,
        "module": "crm",
        "description": "Lista contatos e historico basico do CRM.",
    },
    {
        "code": "contacts.manage",
        "name": "Gerenciar contatos",
        "scope_level": RoleScope.STORE,
        "module": "crm",
        "description": "Cria, edita e etiqueta contatos.",
    },
    {
        "code": "crm.view",
        "name": "Visualizar atendimento",
        "scope_level": RoleScope.STORE,
        "module": "crm",
        "description": "Visualiza conversas, timeline e mensagens.",
    },
    {
        "code": "crm.manage",
        "name": "Operar atendimento",
        "scope_level": RoleScope.STORE,
        "module": "crm",
        "description": "Registra mensagens, notas e altera status.",
    },
    {
        "code": "conversations.assign",
        "name": "Redistribuir atendimento",
        "scope_level": RoleScope.STORE,
        "module": "crm",
        "description": "Atribui ou reatribui conversas para atendentes.",
    },
)


ROLES: Sequence[dict[str, object]] = (
    {
        "code": "platform_superadmin",
        "name": "Superadmin da Plataforma",
        "scope_level": RoleScope.PLATFORM,
        "description": "Acesso total ao control plane.",
        "permissions": [item["code"] for item in PERMISSIONS],
    },
    {
        "code": "company_admin",
        "name": "Administrador da Empresa",
        "scope_level": RoleScope.COMPANY,
        "description": "Gerencia empresas, lojas e usuarios no proprio escopo.",
        "permissions": [
            "companies.view",
            "companies.manage",
            "stores.view",
            "stores.manage",
            "channels.view",
            "channels.manage",
            "meta.view",
            "meta.manage",
            "templates.manage",
            "automations.view",
            "automations.manage",
            "ops.view",
            "audit.view",
            "users.view",
            "users.manage",
            "billing.view",
            "contacts.view",
            "contacts.manage",
            "crm.view",
            "crm.manage",
            "conversations.assign",
        ],
    },
    {
        "code": "store_manager",
        "name": "Gerente da Loja",
        "scope_level": RoleScope.STORE,
        "description": "Acompanha operacao da loja.",
        "permissions": [
            "stores.view",
            "users.view",
            "channels.view",
            "contacts.view",
            "contacts.manage",
            "crm.view",
            "crm.manage",
            "conversations.assign",
            "automations.view",
            "automations.manage",
            "ops.view",
            "audit.view",
        ],
    },
    {
        "code": "store_agent",
        "name": "Atendente da Loja",
        "scope_level": RoleScope.STORE,
        "description": "Opera o atendimento da loja.",
        "permissions": [
            "stores.view",
            "channels.view",
            "contacts.view",
            "contacts.manage",
            "crm.view",
            "crm.manage",
            "automations.view",
            "ops.view",
        ],
    },
)


async def bootstrap_reference_data(session: AsyncSession) -> None:
    existing_permissions = {
        item.code: item
        for item in (await session.scalars(select(Permission))).all()
    }
    for permission_data in PERMISSIONS:
        if permission_data["code"] in existing_permissions:
            continue
        session.add(Permission(**permission_data))
    await session.flush()

    permissions = {
        item.code: item
        for item in (await session.scalars(select(Permission))).all()
    }
    existing_roles = {
        item.code: item
        for item in (await session.scalars(select(Role))).all()
    }
    for role_data in ROLES:
        role = existing_roles.get(role_data["code"])
        if not role:
            role = Role(
                code=role_data["code"],
                name=role_data["name"],
                scope_level=role_data["scope_level"],
                description=role_data["description"],
                is_system=True,
            )
            session.add(role)
            await session.flush()
        role.permissions = [permissions[code] for code in role_data["permissions"]]

    await session.flush()

    if not settings.seed_superadmin:
        await session.commit()
        return

    superadmin = await session.scalar(
        select(PlatformUser).where(PlatformUser.login == settings.superadmin_login)
    )
    if not superadmin:
        superadmin = PlatformUser(
            full_name=settings.superadmin_full_name,
            login=settings.superadmin_login,
            email=str(settings.superadmin_email),
            password_hash=hash_password(settings.superadmin_password),
        )
        session.add(superadmin)
        await session.flush()

    superadmin_role = await session.scalar(select(Role).where(Role.code == "platform_superadmin"))
    existing_assignment = await session.scalar(
        select(PlatformUserRoleAssignment).where(
            PlatformUserRoleAssignment.user_id == superadmin.id,
            PlatformUserRoleAssignment.role_id == superadmin_role.id,
        )
    )
    if not existing_assignment:
        session.add(
            PlatformUserRoleAssignment(
                user_id=superadmin.id,
                role_id=superadmin_role.id,
            )
        )

    await session.commit()
