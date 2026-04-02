"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/src/providers/AuthProvider";

export default function HomePage() {
  const router = useRouter();
  const { isAuthenticated, isBootstrapping } = useAuth();

  useEffect(() => {
    if (isBootstrapping) {
      return;
    }
    router.replace(isAuthenticated ? "/dashboard" : "/login");
  }, [isAuthenticated, isBootstrapping, router]);

  return (
    <main className="splash-screen">
      <section className="splash-screen__card">
        <span className="workspace__eyebrow">AtendeCRM SaaS</span>
        <h1>Preparando ambiente web...</h1>
        <p>Redirecionando para o portal da plataforma.</p>
      </section>
    </main>
  );
}
