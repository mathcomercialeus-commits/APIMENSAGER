# Operacao SaaS

## Endpoints basicos

- health: `GET /api/v1/health`
- login: `POST /api/v1/auth/login`
- portal web: `/`

## Runbook rapido

### Ver logs

```powershell
C:\APIMENEGER\scripts\saas\logs.ps1
C:\APIMENEGER\scripts\saas\logs.ps1 api
C:\APIMENEGER\scripts\saas\logs.ps1 worker
```

```bash
sh ./scripts/saas/logs.sh
sh ./scripts/saas/logs.sh api
sh ./scripts/saas/logs.sh worker
```

### Backup

```powershell
C:\APIMENEGER\scripts\saas\backup-db.ps1
```

```bash
sh ./scripts/saas/backup-db.sh
```

### Restore

```powershell
C:\APIMENEGER\scripts\saas\restore-db.ps1 -InputPath C:\backup.sql
```

```bash
sh ./scripts/saas/restore-db.sh ./infra/compose/backups/backup.sql
```

## Acoes criticas

- restart por loja deve ser feito pelo painel `Operacao`
- cancelamento de assinatura deve ser feito pelo painel `Billing`
- alteracao de credenciais Meta deve ser feita pelo painel `Canais`
- eventos em `dead-letter` podem ser reenfileirados manualmente pelo superadmin no painel `Operacao`
- automacoes oficiais devem ser testadas primeiro em modo manual antes de depender dos gatilhos automaticos em producao
- o painel `Operacao` agora tambem concentra execucoes de automacao com falha, processamento prolongado ou status ignorado
- execucoes de automacao com retry agendado ou dead-letter podem ser acompanhadas e reenfileiradas pelo `Ops`
- a fila critica de automacoes no `Ops` agora aceita filtro por canal e por regra, sem sair do contexto da empresa ou loja selecionada
- a mesma fila critica de automacoes tambem permite recorte por status e periodo, alem de exportacao CSV do resultado visivel
- a fila critica de automacoes tambem suporta ordenacao e paginacao para operacao com alto volume
- as filas criticas de Meta e billing tambem passaram a suportar ordenacao e paginacao no painel `Ops`
- as tres filas criticas do `Ops` agora permitem exportacao CSV do recorte atualmente visivel

## Operacao do superadmin

1. criar empresa
2. criar loja
3. criar usuarios e memberships
4. cadastrar canal oficial
5. salvar credenciais Meta
6. sincronizar templates
7. criar plano e assinatura
8. acompanhar `Ops` e `Auditoria`

## Limitacoes reais

- sem callback HTTPS publico, o recebimento em tempo real da Meta nao funciona
- o worker Celery atual cobre webhooks da Meta, webhooks financeiros, execucoes de automacao e retentativas; ele ainda nao executa restart isolado por tenant
- restart por loja altera a geracao do runtime e registra auditoria, mas ainda depende do runtime/agent obedecer essa troca
- `out_of_hours` hoje depende do horario configurado na propria regra e so dispara na abertura de nova conversa via webhook oficial
