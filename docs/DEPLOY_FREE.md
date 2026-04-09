# Deploy grátis / baixo custo (passo a passo objetivo)

## Render + cron-job.org (recomendado)
1. Suba o repositório no GitHub.
2. No Render, crie Web Service com `node server.js`.
3. Configure variáveis conforme `.env.example`.
4. Valide `GET /health`.
5. No cron-job.org, crie tarefa `POST https://SEU_APP.onrender.com/api/worker/tick` com body JSON:
   `{ "secret": "SEU_WORKER_SECRET" }`
6. Intervalo recomendado: 5 minutos.

## Observações
- Free tier pode dormir; o cron reduz atraso.
- Para persistência robusta, mover para PostgreSQL e object storage.
