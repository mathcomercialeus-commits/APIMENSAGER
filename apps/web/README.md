# Web App SaaS

Interface web Next.js da plataforma SaaS multiempresa e multiloja.

## Escopo implementado nesta etapa

- login e sessao JWT com refresh token
- shell web unica para superadmin, empresa e loja
- dashboard geral
- empresas
- lojas
- usuarios e memberships
- canais WhatsApp + Meta credentials + templates
- automacoes oficiais por loja e canal
- CRM e atendimento
- billing e subscriptions
- operacao por loja, incidentes e restart
- auditoria
- relatorios derivados
- pagina de configuracoes/contexto

## Estrutura principal

```text
apps/web
|-- app
|   |-- (portal)
|   |-- globals.css
|   `-- login
|-- src
|   |-- components
|   |-- features/pages
|   |-- lib
|   |-- providers
|   `-- types
|-- .env.example
|-- next.config.ts
|-- package.json
`-- tsconfig.json
```

## Variaveis de ambiente

Copie `.env.example` para `.env.local` e ajuste:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
```

## Execucao local

```bash
npm install
npm run dev
```

## Observacoes reais

- O frontend esta alinhado aos endpoints existentes do `apps/api`.
- A parte de Meta depende de credenciais reais, templates aprovados e webhook HTTPS publico.
- A tela de automacoes opera end-to-end no modo manual, acompanha execucoes automaticas disparadas por abertura, atribuicao e fora do horario via webhook oficial, e agora exibe retry/dead-letter dessas execucoes.
- A tela de billing agora depende do endpoint `GET /billing/plans/{plan_id}/versions`, que foi adicionado para suportar o portal.
- Ainda nao houve build Next.js validado end-to-end nesta maquina.
