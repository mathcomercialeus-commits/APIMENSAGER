"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren
} from "react";

import { useAuth } from "@/src/providers/AuthProvider";
import type { CompanyRead, StoreRead, UUID } from "@/src/types/api";

interface WorkspaceContextValue {
  companies: CompanyRead[];
  stores: StoreRead[];
  visibleStores: StoreRead[];
  selectedCompanyId: UUID | null;
  selectedStoreId: UUID | null;
  activeCompany: CompanyRead | null;
  activeStore: StoreRead | null;
  isLoading: boolean;
  refreshWorkspace: () => Promise<void>;
  selectCompany: (companyId: UUID | null) => void;
  selectStore: (storeId: UUID | null) => void;
}

const STORAGE_KEY = "atendecrm-saas.workspace";
const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

function loadStoredScope(): { companyId: UUID | null; storeId: UUID | null } {
  if (typeof window === "undefined") {
    return { companyId: null, storeId: null };
  }
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return { companyId: null, storeId: null };
  }
  try {
    const parsed = JSON.parse(raw) as { companyId?: UUID | null; storeId?: UUID | null };
    return { companyId: parsed.companyId || null, storeId: parsed.storeId || null };
  } catch {
    return { companyId: null, storeId: null };
  }
}

export function WorkspaceProvider({ children }: PropsWithChildren) {
  const { apiFetch, isAuthenticated } = useAuth();
  const [companies, setCompanies] = useState<CompanyRead[]>([]);
  const [stores, setStores] = useState<StoreRead[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedCompanyId, setSelectedCompanyId] = useState<UUID | null>(null);
  const [selectedStoreId, setSelectedStoreId] = useState<UUID | null>(null);

  useEffect(() => {
    const stored = loadStoredScope();
    setSelectedCompanyId(stored.companyId);
    setSelectedStoreId(stored.storeId);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ companyId: selectedCompanyId, storeId: selectedStoreId })
    );
  }, [selectedCompanyId, selectedStoreId]);

  const refreshWorkspace = useCallback(async () => {
    if (!isAuthenticated) {
      setCompanies([]);
      setStores([]);
      return;
    }
    setIsLoading(true);
    try {
      const [companiesResponse, storesResponse] = await Promise.all([
        apiFetch<CompanyRead[]>("/companies"),
        apiFetch<StoreRead[]>("/stores")
      ]);
      setCompanies(companiesResponse);
      setStores(storesResponse);
    } finally {
      setIsLoading(false);
    }
  }, [apiFetch, isAuthenticated]);

  useEffect(() => {
    void refreshWorkspace();
  }, [refreshWorkspace]);

  useEffect(() => {
    if (!companies.length && !stores.length) {
      return;
    }

    const activeStore = selectedStoreId ? stores.find((item) => item.id === selectedStoreId) || null : null;
    if (activeStore) {
      if (selectedCompanyId !== activeStore.company_id) {
        setSelectedCompanyId(activeStore.company_id);
      }
      return;
    }

    const companyStillExists = selectedCompanyId
      ? companies.some((item) => item.id === selectedCompanyId)
      : false;
    if (!companyStillExists) {
      const fallback = stores[0]?.company_id || companies[0]?.id || null;
      if (fallback !== selectedCompanyId) {
        setSelectedCompanyId(fallback);
      }
    }
  }, [companies, selectedCompanyId, selectedStoreId, stores]);

  const visibleStores = useMemo(
    () => stores.filter((store) => !selectedCompanyId || store.company_id === selectedCompanyId),
    [selectedCompanyId, stores]
  );

  const activeCompany = useMemo(
    () => companies.find((item) => item.id === selectedCompanyId) || null,
    [companies, selectedCompanyId]
  );

  const activeStore = useMemo(
    () => stores.find((item) => item.id === selectedStoreId) || null,
    [selectedStoreId, stores]
  );

  const selectCompany = useCallback(
    (companyId: UUID | null) => {
      setSelectedCompanyId(companyId);
      setSelectedStoreId((currentStoreId) => {
        if (!currentStoreId) {
          return null;
        }
        const currentStore = stores.find((item) => item.id === currentStoreId);
        if (!currentStore) {
          return null;
        }
        if (companyId && currentStore.company_id !== companyId) {
          return null;
        }
        return currentStoreId;
      });
    },
    [stores]
  );

  const selectStore = useCallback(
    (storeId: UUID | null) => {
      setSelectedStoreId(storeId);
      if (!storeId) {
        return;
      }
      const store = stores.find((item) => item.id === storeId);
      if (store) {
        setSelectedCompanyId(store.company_id);
      }
    },
    [stores]
  );

  const value = useMemo<WorkspaceContextValue>(
    () => ({
      companies,
      stores,
      visibleStores,
      selectedCompanyId,
      selectedStoreId,
      activeCompany,
      activeStore,
      isLoading,
      refreshWorkspace,
      selectCompany,
      selectStore
    }),
    [
      activeCompany,
      activeStore,
      companies,
      isLoading,
      refreshWorkspace,
      selectCompany,
      selectStore,
      selectedCompanyId,
      selectedStoreId,
      stores,
      visibleStores
    ]
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace(): WorkspaceContextValue {
  const context = useContext(WorkspaceContext);
  if (!context) {
    throw new Error("useWorkspace precisa estar dentro de WorkspaceProvider");
  }
  return context;
}
