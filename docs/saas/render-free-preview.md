# Preview gratis no Render

Este projeto pode ser publicado no Render para um preview rapido com o arquivo [render.yaml](/C:/APIMENEGER/render.yaml).

## O que esse preview sobe

- `atendecrm-preview-web`: frontend Next.js em `free web service`
- `atendecrm-preview-api`: API FastAPI em `free web service`
- `atendecrm-preview-db`: Render Postgres `free`
- `atendecrm-preview-kv`: Render Key Value `free`

## Limitacoes reais

- O Render informa que `free` nao esta disponivel para `background workers`, entao o preview roda com `CELERY_TASK_ALWAYS_EAGER=true`.
- As tarefas assincronas sao executadas inline na API. Isso serve para demonstracao, nao para producao.
- O Render informa que `free web services` entram em idle apos 15 minutos sem trafego e podem levar cerca de 1 minuto para voltar.
- O Render informa que o `free Postgres` expira 30 dias apos a criacao e nao oferece backups.
- O Render informa que o `free Key Value` e apenas em memoria; se reiniciar, os dados somem.

## Quando usar

Use este modo apenas para:

- ver a interface no navegador
- testar login e navegacao principal
- validar se o deploy do monorepo funciona
- demonstrar a plataforma para avaliacao inicial

Nao use esse modo para:

- operacao real com clientes
- producao com Meta webhooks
- producao com billing
- validacao de confiabilidade da fila

## O que voce precisa antes

- uma conta no Render
- o projeto em um repositorio GitHub, GitLab ou equivalente suportado pelo Render

## Como criar

1. Envie o projeto para um repositorio Git.
2. No Render, escolha `New +`.
3. Use a opcao de `Blueprint`.
4. Aponte para o repositorio que contem [render.yaml](/C:/APIMENEGER/render.yaml).
5. No primeiro deploy, o Render vai pedir os campos marcados com `sync: false`:
   - `SUPERADMIN_PASSWORD`
   - `META_GLOBAL_APP_SECRET`
   - `META_GLOBAL_VERIFY_TOKEN`
   - `ASAAS_API_KEY`
   - `ASAAS_WEBHOOK_AUTH_TOKEN`
6. Conclua a criacao.

## Login inicial

- login: `admin`
- senha: a que voce informar no campo `SUPERADMIN_PASSWORD`

## Ajustes que podem ser necessarios

- Se o nome publico dos servicos ficar diferente de `atendecrm-preview-web` ou `atendecrm-preview-api`, ajuste no Render:
  - `NEXT_PUBLIC_API_BASE_URL`
  - `BACKEND_CORS_ORIGINS`

## Fontes oficiais

- [Render free](https://render.com/docs/free)
- [Render pricing](https://render.com/pricing)
- [Render blueprint spec](https://render.com/docs/blueprint-spec)
- [Render web services](https://render.com/docs/web-services)
- [Render background workers](https://render.com/docs/background-workers)
- [Render Postgres](https://render.com/docs/postgresql)
- [Render Key Value](https://render.com/docs/key-value)
