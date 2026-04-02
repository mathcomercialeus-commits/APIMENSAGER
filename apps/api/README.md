# AtendeCRM SaaS API

Backend FastAPI da plataforma web SaaS multiempresa e multiloja.

## Modulos atuais

- autenticacao JWT com refresh token
- empresas e lojas
- usuarios, roles, permissions e memberships
- billing com Asaas
- CRM de contatos e conversas
- integracao oficial com Meta Cloud API
- automacoes oficiais por loja/canal com execucao assíncrona
- operacao por loja, incidentes e restart logico
- auditoria

## Execucao local

1. Copie `.env.example` para `.env`
2. Ajuste `DATABASE_URL`, segredos JWT e superadmin
3. Instale dependencias
4. Rode:

```bash
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Execucao via container

Use o Dockerfile em [Dockerfile](/C:/APIMENEGER/apps/api/Dockerfile) ou a stack completa em [docker-compose.saas.yml](/C:/APIMENEGER/infra/compose/docker-compose.saas.yml).

## Worker assincrono

Para processar webhooks e jobs em segundo plano:

```bash
celery -A app.workers.celery_app.celery_app worker --loglevel=INFO
```

## Observacoes reais

- o webhook da Meta exige HTTPS publico
- o billing real exige `ASAAS_API_KEY`
- o modulo de automacoes ja executa regras manualmente e por gatilho automatico no CRM/webhook; agora tambem possui retry com backoff e dead-letter no worker
- o restart por loja e persistido/logico; ele nao recicla um processo exclusivo por tenant
