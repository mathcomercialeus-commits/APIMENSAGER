# ETAPA 3 - Billing

## Provider inicial

- Asaas

## Escopo implementado

- planos
- versions de plano
- customer financeiro por empresa
- subscription por empresa ou loja
- invoices
- payments
- payment events
- provider events
- webhook do Asaas
- processamento assincrono via Celery

## Regras desta etapa

- superadmin cria planos
- superadmin cria e cancela subscriptions
- empresa cliente pode consultar seu proprio billing quando tiver permissao `billing.view`
- customer no Asaas e criado sob demanda no primeiro fluxo de subscription ou sync manual

## Credenciais reais necessarias

Preencher em `apps/api/.env`:

- `ASAAS_API_BASE_URL`
- `ASAAS_API_KEY`
- `ASAAS_WEBHOOK_AUTH_TOKEN`

## Limitacoes reais

- o fluxo de cartao foi modelado no nivel da subscription, mas checkout/tokenizacao de cartao do cliente ainda nao foi implementado nesta etapa
- o webhook depende de configuracao oficial no painel do Asaas
- o `provider_event_id` e deduzido a partir do evento e do id da cobranca ou subscription quando o payload nao trouxer um identificador unico de evento
- a ingestao do webhook agora entra em fila; sem Redis/worker saudavel, a API cai em modo de contingencia inline
- retries automaticos e dead-letter ja foram modelados para eventos financeiros
- o motor de dunning automatico e notificacoes de vencimento ainda entra na etapa seguinte do billing operacional
