# AtendeCRM SaaS Platform

Plataforma web SaaS multiempresa e multiloja para atendimento e CRM via WhatsApp Business Platform, usando exclusivamente integracoes oficiais da Meta.

## Escopo atual

- `apps/api`: backend FastAPI tenant-aware
- `apps/web`: frontend Next.js do portal SaaS
- multiempresa, multiloja e RBAC
- billing SaaS com Asaas
- CRM de contatos e conversas
- integracao oficial com Meta Cloud API
- automacoes oficiais por loja e canal
- status operacional por loja
- restart logico por loja com auditoria
- worker Celery para webhooks da Meta, billing e fila operacional
- painel `Ops` com filas criticas de Meta, billing e automacoes
- filtros operacionais por regra e canal na fila critica de automacoes
- exportacao CSV e recorte por status/periodo na fila critica de automacoes
- paginacao e ordenacao na fila critica de automacoes
- paginacao e ordenacao nas filas criticas de Meta e billing
- exportacao CSV nas filas criticas de Meta, billing e automacoes
- deploy base com Docker Compose + Nginx

## Estrutura principal

```text
C:\APIMENEGER
|-- apps
|   |-- api
|   `-- web
|-- docs
|   `-- saas
|-- infra
|   |-- compose
|   `-- nginx
|-- packages
|-- scripts
|   `-- saas
`-- workers
```

## Subida rapida da plataforma SaaS

1. Copie o arquivo de ambiente:

```powershell
Copy-Item C:\APIMENEGER\infra\compose\.env.saas.example C:\APIMENEGER\infra\compose\.env.saas
```

2. Preencha pelo menos:

- `POSTGRES_PASSWORD`
- `JWT_SECRET_KEY`
- `DATA_ENCRYPTION_SECRET`
- `SUPERADMIN_PASSWORD`
- `ASAAS_API_KEY` quando usar billing real
- credenciais reais da Meta quando ligar canais oficiais

3. Suba a stack:

```powershell
C:\APIMENEGER\scripts\saas\deploy-compose.ps1
```

ou:

```bash
sh ./scripts/saas/deploy-compose.sh
```

4. Acesse:

- portal web: [http://localhost:8080](http://localhost:8080)
- API: [http://localhost:8080/api/v1/health](http://localhost:8080/api/v1/health)

## Documentacao SaaS

- [Arquitetura](C:/APIMENEGER/docs/saas/architecture.md)
- [Banco de dados](C:/APIMENEGER/docs/saas/database-model.md)
- [Billing](C:/APIMENEGER/docs/saas/billing.md)
- [Automacoes oficiais](C:/APIMENEGER/docs/saas/automations.md)
- [Estrutura do projeto](C:/APIMENEGER/docs/saas/project-structure.md)
- [Deploy SaaS](C:/APIMENEGER/docs/saas/deployment.md)
- [Operacao](C:/APIMENEGER/docs/saas/operations.md)
- [Webhooks Meta](C:/APIMENEGER/docs/saas/meta-webhooks.md)
- [Hardening](C:/APIMENEGER/docs/saas/hardening.md)

## Limites reais neste ponto

- O webhook oficial da Meta continua exigindo callback HTTPS publico.
- O restart por loja implementado hoje e logico/persistido; ele nao reinicia um processo exclusivo por tenant.
- Redis ja esta sendo consumido por um worker Celery dedicado para webhooks da Meta, billing, retry e dead-letter operacional.
- O modulo de automacoes ja suporta execucao oficial via fila e envio pela Meta, incluindo gatilhos automaticos para conversa aberta, atribuicao e fora do horario na entrada oficial via webhook.
- As automacoes agora usam retry com backoff e dead-letter, com reenfileiramento manual pelo superadmin no painel `Ops`.
- O frontend SaaS foi escrito e conectado aos endpoints reais, mas ainda nao teve build Next.js validado nesta maquina porque `node` e `npm` nao estao instalados no ambiente local desta sessao.

## Regras de integracao com a Meta

- sem WhatsApp Web automatizado
- sem scraping
- sem bibliotecas nao oficiais
- templates aprovados para mensagens fora da janela de 24h
- consentimento e opt-in quando aplicavel

## Scripts uteis

```powershell
C:\APIMENEGER\scripts\saas\deploy-compose.ps1
C:\APIMENEGER\scripts\saas\backup-db.ps1
C:\APIMENEGER\scripts\saas\restore-db.ps1 -InputPath C:\caminho\backup.sql
C:\APIMENEGER\scripts\saas\logs.ps1
```

```bash
sh ./scripts/saas/deploy-compose.sh
sh ./scripts/saas/backup-db.sh
sh ./scripts/saas/restore-db.sh ./infra/compose/backups/arquivo.sql
sh ./scripts/saas/logs.sh
```
