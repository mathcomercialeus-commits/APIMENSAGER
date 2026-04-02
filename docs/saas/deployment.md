# Deploy SaaS

## Stack de deploy atual

- `apps/api` em container Python 3.12
- `apps/api` worker Celery dedicado
- `apps/web` em container Next.js standalone
- PostgreSQL 16
- Redis 7
- Nginx como reverse proxy
- Docker Compose em [docker-compose.saas.yml](/C:/APIMENEGER/infra/compose/docker-compose.saas.yml)

## Arquivos de infraestrutura

- [apps/api/Dockerfile](/C:/APIMENEGER/apps/api/Dockerfile)
- [apps/web/Dockerfile](/C:/APIMENEGER/apps/web/Dockerfile)
- [docker-compose.saas.yml](/C:/APIMENEGER/infra/compose/docker-compose.saas.yml)
- [saas.conf](/C:/APIMENEGER/infra/nginx/saas.conf)
- [.env.saas.example](/C:/APIMENEGER/infra/compose/.env.saas.example)

## Procedimento

1. Copie `.env.saas.example` para `.env.saas`.
2. Ajuste os segredos obrigatorios.
3. Rode:

```powershell
C:\APIMENEGER\scripts\saas\deploy-compose.ps1
```

ou:

```bash
sh ./scripts/saas/deploy-compose.sh
```

## Porta de entrada

- Nginx exposto em `http://HOST:8080`
- Frontend em `/`
- API em `/api/v1`

## Variaveis obrigatorias

- `POSTGRES_PASSWORD`
- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `DATA_ENCRYPTION_SECRET`
- `SUPERADMIN_PASSWORD`

## Variaveis externas opcionais mas importantes

- `ASAAS_API_KEY`
- `ASAAS_WEBHOOK_AUTH_TOKEN`
- `META_GLOBAL_APP_SECRET`
- `META_GLOBAL_VERIFY_TOKEN`
- `RUNTIME_AGENT_TOKEN`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `QUEUE_MAX_ATTEMPTS`
- `QUEUE_RETRY_BACKOFF_SECONDS`
- `QUEUE_RETRY_BACKOFF_MAX_SECONDS`

## Observacao real

O Compose atual sobe a plataforma principal com um worker Celery dedicado para webhooks da Meta, webhooks do billing e futuros jobs operacionais. O restart por loja continua sendo logico/persistido; ele ainda nao recicla um processo exclusivo por tenant.
