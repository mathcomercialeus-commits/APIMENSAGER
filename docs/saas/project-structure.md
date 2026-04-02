# ETAPA 1 - Estrutura de Pastas

```text
C:\APIMENEGER
|-- apps
|   |-- api
|   `-- web
|-- docs
|   `-- saas
|-- infra
|   |-- compose
|   |-- k8s
|   `-- terraform
|-- packages
|   |-- billing
|   |-- config
|   |-- contracts
|   |-- meta
|   |-- tenanting
|   `-- ui
|-- workers
|   |-- orchestrator
|   `-- store-runtime
|-- backend
|-- frontend
`-- scripts
```

## Leitura da estrutura

- `apps/api`: nova API SaaS FastAPI
- `apps/web`: nova interface web Next.js
- `packages/contracts`: DTOs e contratos compartilhados
- `packages/tenanting`: helpers e politicas de tenant
- `packages/billing`: adaptadores de billing
- `packages/meta`: integracao oficial Meta
- `workers/orchestrator`: comandos globais, restart e suporte operacional
- `workers/store-runtime`: jobs por loja, automacao e processamento
- `infra/k8s`: manifests para producao
- `infra/terraform`: base de cloud

## Convivencia com a base atual

A estrutura antiga nao foi removida nesta etapa.

Motivo:

- preservar o trabalho anterior enquanto a plataforma e reestruturada
- permitir migracao controlada para o modelo SaaS
