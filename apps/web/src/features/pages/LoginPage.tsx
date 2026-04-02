"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, getApiBaseUrl } from "@/src/lib/api";
import { useAuth } from "@/src/providers/AuthProvider";

export function LoginPage() {
  const router = useRouter();
  const { login, isAuthenticated, isBootstrapping } = useAuth();
  const [loginValue, setLoginValue] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isBootstrapping && isAuthenticated) {
      router.replace("/dashboard");
    }
  }, [isAuthenticated, isBootstrapping, router]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login(loginValue, password);
    } catch (exception) {
      setError(exception instanceof ApiError ? exception.message : "Falha ao iniciar sessao.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-page__hero">
        <span className="login-page__eyebrow">Plataforma SaaS oficial</span>
        <h1>Atendimento WhatsApp com CRM, billing e operacao multiloja.</h1>
        <p>
          Portal web para superadmin, empresas clientes e lojas operarem o atendimento dentro
          do ecossistema oficial da Meta.
        </p>

        <div className="feature-grid">
          <article>
            <strong>Superadmin central</strong>
            <span>Status das lojas, billing, suporte tecnico e restart por loja.</span>
          </article>
          <article>
            <strong>CRM operacional</strong>
            <span>Conversas, canais oficiais, timeline e contexto por empresa e loja.</span>
          </article>
          <article>
            <strong>Billing recorrente</strong>
            <span>Planos, assinaturas, faturas, inadimplencia e suspensao controlada.</span>
          </article>
        </div>
      </section>

      <section className="login-card">
        <span className="login-card__eyebrow">Entrar no portal</span>
        <h2>Painel corporativo</h2>
        <p>Use seu usuario global da plataforma para acessar o ambiente SaaS.</p>

        <form className="form-grid" onSubmit={handleSubmit}>
          <label>
            <span>Login ou e-mail</span>
            <input value={loginValue} onChange={(event) => setLoginValue(event.target.value)} required />
          </label>
          <label>
            <span>Senha</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>

          {error ? <div className="callout callout--danger">{error}</div> : null}

          <button type="submit" className="button button--primary" disabled={isSubmitting}>
            {isSubmitting ? "Entrando..." : "Entrar"}
          </button>
        </form>

        <div className="server-hint">
          <span>API base atual</span>
          <code>{getApiBaseUrl()}</code>
        </div>
      </section>
    </main>
  );
}
