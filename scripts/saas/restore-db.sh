#!/usr/bin/env sh
set -eu

if [ $# -ne 1 ]; then
  echo "Uso: ./scripts/saas/restore-db.sh /caminho/do/backup.sql"
  exit 1
fi

BACKUP_FILE="$1"
COMPOSE_DIR="$(cd "$(dirname "$0")/../../infra/compose" && pwd)"
cd "$COMPOSE_DIR"

docker compose --env-file .env.saas -f docker-compose.saas.yml exec -T postgres \
  sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"' < "$BACKUP_FILE"

echo "Restore concluido."
