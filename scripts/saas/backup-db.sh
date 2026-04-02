#!/usr/bin/env sh
set -eu

COMPOSE_DIR="$(cd "$(dirname "$0")/../../infra/compose" && pwd)"
cd "$COMPOSE_DIR"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
mkdir -p ./backups
docker compose --env-file .env.saas -f docker-compose.saas.yml exec -T postgres \
  sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  > "./backups/atendecrm_saas_${TIMESTAMP}.sql"

echo "Backup salvo em ./backups/atendecrm_saas_${TIMESTAMP}.sql"
