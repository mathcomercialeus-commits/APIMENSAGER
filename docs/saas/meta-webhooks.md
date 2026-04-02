# Meta Webhooks e Cloud API

## Requisito real

A Meta exige webhook HTTPS publico para entregar:

- mensagens inbound
- status `sent`, `delivered`, `read`, `failed`
- eventos da Cloud API

## O que pode ficar privado

- PostgreSQL
- Redis
- Nginx interno
- painel web
- API administrativa

## O que precisa de exposicao publica

- callback oficial de webhook da Meta

## Estrategias recomendadas

### Producao SaaS

- publicar Nginx com HTTPS real
- terminar TLS no Nginx ou no balanceador
- apontar a Meta para:
  - `GET /api/v1/meta/webhooks`
  - `POST /api/v1/meta/webhooks`

## Fluxo operacional implementado

1. a API recebe o webhook oficial
2. valida assinatura quando houver `app_secret`
3. persiste o `webhook_event`
4. enfileira o processamento no worker Celery
5. o worker resolve canal, contato, conversa, mensagens e status
6. o evento fica marcado como `processed`, `ignored`, `retry_scheduled` ou `dead_lettered`

Se a fila estiver indisponivel no momento do recebimento, a API faz fallback inline para nao perder o evento.

## Retry e dead-letter

- falhas transitorias entram em `retry_scheduled`
- o backoff e configurado por variaveis de ambiente
- ao atingir o limite de tentativas, o evento vai para `dead_lettered`
- o superadmin pode reenfileirar manualmente eventos Meta pelo painel `Operacao`

### Multi-canal

O backend atual suporta:

- webhook global
- webhook por canal
- roteamento por `phone_number_id`

## Dependencias externas reais

- numero oficial aprovado
- `phone_number_id`
- `business_account_id`
- `access_token`
- `app_secret`
- `verify_token`
- templates aprovados quando a janela de 24h estiver fechada

## Limite real atual

O codigo ja envia e recebe payloads oficiais, com ingestao assincrona via Celery, retry controlado e dead-letter, mas a validacao end-to-end com a Meta ainda depende de credenciais reais e callback publico configurado fora desta maquina.
