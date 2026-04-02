# Hardening SaaS

## Aplicacao

- trocar todos os segredos do `.env.saas`
- manter `DEBUG=false`
- manter `AUTO_CREATE_TABLES=false` em producao
- revisar CORS para os dominios reais do portal

## Banco

- senha forte no PostgreSQL
- backup diario e teste de restore
- acesso ao banco restrito a rede privada

## Nginx

- habilitar HTTPS real
- colocar rate limiting por IP nas rotas de auth e webhooks
- logar `X-Forwarded-For` corretamente atras de load balancer

## Meta

- rotacionar tokens periodicamente
- proteger `app_secret` e `verify_token`
- auditar alteracoes de credenciais pelo painel

## Billing

- validar webhook do Asaas por token
- reconciliar pagamentos com logs e invoices
- monitorar `past_due`, `suspended` e `canceled`

## Operacao por loja

- restringir restart por loja ao superadmin
- exigir motivo do restart
- revisar incidentes nao resolvidos diariamente

## Observabilidade

- centralizar logs JSON
- integrar erro de frontend e backend em Sentry ou equivalente
- expor metricas Prometheus na proxima iteracao operacional
