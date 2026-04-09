# Social Scheduler Lite

Aplicacao web para agendamento de posts com imagem e video, autenticacao admin, dashboard, calendario, filtros, logs e arquitetura pronta para hospedagem simples no Render.

## Estrutura

```text
C:\APIMENEGER
|-- app.js
|-- index.html
|-- server.js
|-- styles.css
|-- data
|   |-- store.json
|   `-- uploads
|-- docs
|   |-- ARCHITECTURE.md
|   `-- DEPLOY_FREE.md
|-- scripts
|   `-- smoke-test.sh
`-- render.yaml
```

## Funcionalidades

- login de administrador
- dashboard com estatisticas
- upload de imagem e video
- criacao, edicao e exclusao de posts
- agendamento com bloqueio de datas passadas
- calendario mensal
- logs de publicacao
- retries com backoff para falhas temporarias
- endpoint manual de tick para cron externo

## Rodar localmente

1. Copie `.env.example` para `.env`.
2. Defina `AUTH_SECRET`, `WORKER_SECRET` e `ADMIN_PASSWORD`.
3. Rode:

```bash
node server.js
```

4. Acesse [http://localhost:8080](http://localhost:8080).

## Variaveis de ambiente

- `PORT`
- `NODE_ENV`
- `APP_URL`
- `DATA_DIR`
- `AUTH_SECRET`
- `WORKER_SECRET`
- `ADMIN_USER`
- `ADMIN_PASSWORD`
- `MAX_UPLOAD_MB`

Em `production`, o servidor falha no boot se `AUTH_SECRET`, `WORKER_SECRET` ou `ADMIN_PASSWORD` estiverem ausentes ou com valores inseguros.

## Deploy no Render

O arquivo [render.yaml](C:/APIMENEGER/render.yaml) ja prepara:

- web service Node
- health check em `/health`
- geracao automatica de `AUTH_SECRET` e `WORKER_SECRET`
- exigencia manual de `ADMIN_PASSWORD`

Depois do deploy:

1. abra o servico no Render
2. configure `ADMIN_PASSWORD` na aba `Environment`
3. faca `Manual Deploy`
4. teste `/health`

## Testes uteis

```bash
npm run check
npm run smoke
```
