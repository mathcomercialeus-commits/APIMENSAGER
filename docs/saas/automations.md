# Automacoes oficiais

## Escopo atual

O modulo de automacoes da plataforma SaaS foi desenhado para operar apenas com os recursos oficiais do ecossistema da Meta.

Hoje, o fluxo entregue end-to-end cobre:

- cadastro de regras por loja
- restricao opcional por canal WhatsApp
- execucao assincrona via worker Celery
- retry com backoff exponencial e dead-letter para falhas de automacao
- gatilhos automaticos conectados ao fluxo operacional:
  - `conversation_opened`
  - `conversation_assigned`
  - `out_of_hours` quando uma nova conversa entra via webhook oficial da Meta
- acoes oficiais:
  - `send_text`
  - `send_template`
  - `close_conversation`
- historico de execucoes por regra
- execucao manual controlada pelo portal web

## O que ja funciona

### Cadastro de regras

Endpoint base:

- `GET /api/v1/automations/rules`
- `POST /api/v1/automations/rules`
- `PATCH /api/v1/automations/rules/{rule_id}`

Campos principais:

- `store_id`
- `channel_id`
- `trigger_type`
- `action_type`
- `priority`
- `respect_customer_window`
- `message_body`
- `template_name`
- `template_language_code`
- `settings`

### Execucao manual

Uma regra pode ser executada manualmente em uma conversa valida:

- `POST /api/v1/automations/rules/{rule_id}/execute`

Essa chamada:

1. grava `automation_execution`
2. audita a solicitacao
3. enfileira a execucao no worker
4. usa a Meta Cloud API quando a acao exige envio oficial

### Gatilhos automaticos ja ligados

- `conversation_opened`
  - dispara quando uma conversa e criada pelo CRM web
  - dispara quando uma nova conversa nasce por mensagem inbound via webhook oficial da Meta
- `conversation_assigned`
  - dispara quando a conversa recebe um responsavel no CRM
  - tambem pode disparar na atribuicao inicial durante a criacao da conversa
- `out_of_hours`
  - dispara somente quando uma nova conversa entra por webhook oficial da Meta fora da janela configurada
  - nesta etapa, ele nao e reavaliado em toda nova mensagem inbound da mesma conversa

### Configuracao de horario para `out_of_hours`

Use `settings.business_hours` na regra:

```json
{
  "business_hours": {
    "timezone": "America/Manaus",
    "weekdays": [0, 1, 2, 3, 4],
    "start": "08:00",
    "end": "18:00"
  }
}
```

Padrao assumido quando o bloco nao for informado:

- timezone da loja
- segunda a sexta
- `08:00` ate `18:00`

## Regras oficiais da Meta respeitadas

- texto livre fora da janela de 24h nao deve ser enviado quando `respect_customer_window=true`
- mensagens fora da janela exigem template aprovado
- templates dependem de nome, idioma e vinculacao correta ao canal
- credenciais do canal precisam estar ativas

## Limitacoes reais neste ponto

- o modo **manual** esta pronto de ponta a ponta
- os gatilhos `conversation_opened` e `conversation_assigned` ja estao ligados ao CRM real
- o gatilho `out_of_hours` ja funciona para novas conversas que entram pela Meta Cloud API
- ainda nao existe reprocessamento automatico de `out_of_hours` para cada nova mensagem de uma conversa ja aberta
- a execucao da acao `send_template` depende de template aprovado e sincronizado para o canal
- o recebimento em tempo real da Meta continua exigindo webhook HTTPS publico

## Retry e dead-letter

- automacoes falhas entram em nova tentativa com backoff exponencial
- o limite de tentativas usa os mesmos parametros globais da fila:
  - `QUEUE_MAX_ATTEMPTS`
  - `QUEUE_RETRY_BACKOFF_SECONDS`
  - `QUEUE_RETRY_BACKOFF_MAX_SECONDS`
- quando o limite e atingido, a execucao fica marcada como `dead_lettered`
- o superadmin pode reenfileirar manualmente essas execucoes pelo painel `Operacao`

## Operacao recomendada

1. cadastrar a regra pela loja correta
2. testar manualmente em uma conversa controlada
3. validar janela de 24h, template e credenciais
4. acompanhar o historico de execucoes no portal
5. so depois ligar gatilhos automaticos quando o orquestrador dessa etapa entrar em producao
