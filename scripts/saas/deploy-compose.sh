#!/usr/bin/env sh
set -eu

COMPOSE_DIR="$(cd "$(dirname "$0")/../../infra/compose" && pwd)"
ENV_FILE="$COMPOSE_DIR/.env.saas"
ENV_EXAMPLE="$COMPOSE_DIR/.env.saas.example"

if [ ! -f "$ENV_FILE" ]; then
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  echo "Arquivo .env.saas criado a partir do exemplo. Revise as credenciais antes do primeiro uso."
fi

cd "$COMPOSE_DIR"
docker compose --env-file .env.saas -f docker-compose.saas.yml up -d --build
