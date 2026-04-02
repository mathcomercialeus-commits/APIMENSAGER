#!/usr/bin/env sh
set -eu

COMPOSE_DIR="$(cd "$(dirname "$0")/../../infra/compose" && pwd)"
cd "$COMPOSE_DIR"

if [ "${1:-}" != "" ]; then
  docker compose --env-file .env.saas -f docker-compose.saas.yml logs -f "$1"
else
  docker compose --env-file .env.saas -f docker-compose.saas.yml logs -f
fi
