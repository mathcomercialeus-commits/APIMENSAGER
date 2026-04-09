# Arquitetura (execução completa sem pausa)

## Fluxo fim-a-fim
1. Login admin (`/api/auth/login`).
2. Upload de mídia (`/api/upload`).
3. Criação de post (`/api/posts`).
4. Worker processa agendamentos (`setInterval` + `/api/worker/tick`).
5. Status e logs atualizam dashboard.

## Estratégia anti-hibernação
- Tick interno a cada 30s.
- Catch-up quando qualquer rota `/api/*` é chamada.
- Tick externo por cron (recomendado) para reduzir atraso em planos free.

## Camada de integração social
- `publishToNetworkMock` simula publicação.
- Troca futura: criar adaptadores reais por rede e manter o mesmo contrato de retorno.
