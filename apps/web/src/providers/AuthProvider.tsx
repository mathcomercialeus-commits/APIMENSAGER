"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren
} from "react";
import { useRouter } from "next/navigation";

import { ApiError, requestJson, type ApiRequestOptions, type ApiRequester } from "@/src/lib/api";
import type { CurrentUserRead, TokenResponse } from "@/src/types/api";

interface StoredSession {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  user: CurrentUserRead;
}

interface AuthContextValue {
  user: CurrentUserRead | null;
  isAuthenticated: boolean;
  isBootstrapping: boolean;
  apiFetch: ApiRequester;
  login: (login: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  replaceUser: (user: CurrentUserRead) => void;
}

const STORAGE_KEY = "atendecrm-saas.session";
const AuthContext = createContext<AuthContextValue | null>(null);

function toStoredSession(tokens: TokenResponse): StoredSession {
  return {
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
    expiresIn: tokens.expires_in,
    user: tokens.user
  };
}

function loadStoredSession(): StoredSession | null {
  if (typeof window === "undefined") {
    return null;
  }
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as StoredSession;
  } catch {
    window.localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

export function AuthProvider({ children }: PropsWithChildren) {
  const router = useRouter();
  const [session, setSession] = useState<StoredSession | null>(null);
  const [isBootstrapping, setIsBootstrapping] = useState(true);
  const sessionRef = useRef<StoredSession | null>(null);

  useEffect(() => {
    const stored = loadStoredSession();
    setSession(stored);
    sessionRef.current = stored;
    setIsBootstrapping(false);
  }, []);

  useEffect(() => {
    sessionRef.current = session;
    if (typeof window === "undefined") {
      return;
    }
    if (session) {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }, [session]);

  const replaceUser = useCallback((user: CurrentUserRead) => {
    setSession((current) => (current ? { ...current, user } : current));
  }, []);

  const refreshSession = useCallback(async (): Promise<StoredSession> => {
    const current = sessionRef.current;
    if (!current?.refreshToken) {
      throw new ApiError("Sessao expirada.", 401, null);
    }
    const refreshed = await requestJson<TokenResponse>("/auth/refresh", {
      method: "POST",
      body: { refresh_token: current.refreshToken }
    });
    const nextSession = toStoredSession(refreshed);
    setSession(nextSession);
    return nextSession;
  }, []);

  const logout = useCallback(async () => {
    const current = sessionRef.current;
    if (current?.refreshToken) {
      try {
        await requestJson("/auth/logout", {
          method: "POST",
          body: { refresh_token: current.refreshToken },
          accessToken: current.accessToken
        });
      } catch {
        // Mantemos logout local.
      }
    }
    setSession(null);
    router.replace("/login");
  }, [router]);

  const login = useCallback(
    async (loginValue: string, password: string) => {
      const response = await requestJson<TokenResponse>("/auth/login", {
        method: "POST",
        body: { login: loginValue, password }
      });
      setSession(toStoredSession(response));
      router.replace("/dashboard");
    },
    [router]
  );

  const apiFetch = useCallback(
    async <T,>(path: string, options: ApiRequestOptions = {}): Promise<T> => {
      const current = sessionRef.current;
      if (!current?.accessToken) {
        throw new ApiError("Sessao expirada.", 401, null);
      }
      try {
        return await requestJson<T>(path, {
          ...options,
          accessToken: current.accessToken
        });
      } catch (error) {
        if (!(error instanceof ApiError) || error.status !== 401 || !current.refreshToken) {
          throw error;
        }
        try {
          const refreshed = await refreshSession();
          return await requestJson<T>(path, {
            ...options,
            accessToken: refreshed.accessToken
          });
        } catch (refreshError) {
          setSession(null);
          router.replace("/login");
          throw refreshError;
        }
      }
    },
    [refreshSession, router]
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      user: session?.user ?? null,
      isAuthenticated: Boolean(session?.accessToken),
      isBootstrapping,
      apiFetch,
      login,
      logout,
      replaceUser
    }),
    [apiFetch, isBootstrapping, login, logout, replaceUser, session]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth precisa estar dentro de AuthProvider");
  }
  return context;
}
