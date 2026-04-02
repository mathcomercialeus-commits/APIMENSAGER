import type { CompanyRead, CurrentUserRead, StoreRead, UUID } from "@/src/types/api";

export function isSuperadmin(user: CurrentUserRead | null): boolean {
  return Boolean(user?.platform_roles.some((role) => role.role_code === "superadmin"));
}

export function resolveScopedCompanyId(
  selectedCompanyId: UUID | null,
  selectedStoreId: UUID | null,
  stores: StoreRead[],
  companies: CompanyRead[]
): UUID | null {
  if (selectedStoreId) {
    return stores.find((item) => item.id === selectedStoreId)?.company_id || selectedCompanyId;
  }
  return selectedCompanyId || companies[0]?.id || null;
}

export function resolveScopedStoreId(selectedStoreId: UUID | null): UUID | null {
  return selectedStoreId;
}
