import type { CurrentUserRead } from "@/src/types/api";

export interface NavigationItem {
  href: string;
  label: string;
  hint: string;
}

function hasAnyPermission(user: CurrentUserRead, permissions: string[]): boolean {
  return permissions.some((permission) => user.permissions.includes(permission));
}

export function buildNavigation(user: CurrentUserRead): NavigationItem[] {
  const isSuperadmin = user.platform_roles.some((role) => role.role_code === "superadmin");
  const items: NavigationItem[] = [
    { href: "/dashboard", label: "Dashboard", hint: "Visao consolidada da plataforma" }
  ];

  if (isSuperadmin || user.company_memberships.length > 0) {
    items.push(
      { href: "/companies", label: "Empresas", hint: "Clientes, situacao comercial e escopo" },
      { href: "/stores", label: "Lojas", hint: "Unidades, heartbeat e configuracao operacional" }
    );
  }

  if (isSuperadmin || hasAnyPermission(user, ["users.view", "users.manage"])) {
    items.push({ href: "/users", label: "Usuarios", hint: "RBAC, memberships e equipe" });
  }

  if (isSuperadmin || hasAnyPermission(user, ["channels.view", "channels.manage", "meta.view", "meta.manage"])) {
    items.push({
      href: "/channels",
      label: "Canais",
      hint: "WhatsApp oficial, credenciais e templates"
    });
  }

  if (isSuperadmin || hasAnyPermission(user, ["automations.view", "automations.manage"])) {
    items.push({
      href: "/automations",
      label: "Automacoes",
      hint: "Regras oficiais por loja, canal e conversa"
    });
  }

  if (isSuperadmin || hasAnyPermission(user, ["contacts.view", "crm.view", "crm.manage"])) {
    items.push({ href: "/crm", label: "CRM", hint: "Atendimento, contatos e conversas" });
  }

  if (isSuperadmin || hasAnyPermission(user, ["billing.view"])) {
    items.push({ href: "/billing", label: "Billing", hint: "Planos, assinaturas e faturas" });
  }

  if (isSuperadmin || hasAnyPermission(user, ["ops.view"])) {
    items.push({ href: "/ops", label: "Operacao", hint: "Status tecnico, incidentes e restart" });
  }

  items.push({ href: "/reports", label: "Relatorios", hint: "Indicadores derivados do uso da plataforma" });

  if (isSuperadmin || hasAnyPermission(user, ["audit.view"])) {
    items.push({ href: "/audit", label: "Auditoria", hint: "Trilha de acoes e eventos administrativos" });
  }

  items.push({ href: "/settings", label: "Configuracoes", hint: "Sessao, escopo e parametros do portal" });
  return items;
}
