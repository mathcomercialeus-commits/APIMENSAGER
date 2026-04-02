"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/src/providers/AuthProvider";

export function AuthGate({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { isAuthenticated, isBootstrapping } = useAuth();

  useEffect(() => {
    if (!isBootstrapping && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isAuthenticated, isBootstrapping, router]);

  if (isBootstrapping || !isAuthenticated) {
    return (
      <main className="splash-screen">
        <section className="splash-screen__card">
          <span className="workspace__eyebrow">Autenticacao</span>
          <h1>Carregando sessao...</h1>
          <p>Validando acesso ao portal da plataforma.</p>
        </section>
      </main>
    );
  }

  return <>{children}</>;
}
