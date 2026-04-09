#!/usr/bin/env bash
set -euo pipefail
TMP_DATA_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DATA_DIR"' EXIT
AUTH_SECRET=smoke-auth-secret \
WORKER_SECRET=smoke-worker-secret \
ADMIN_PASSWORD=SmokePass123! \
DATA_DIR="$TMP_DATA_DIR" \
NODE_ENV=production \
node server.js > /tmp/scheduler.log 2>&1 &
PID=$!
sleep 1
curl -sSf http://localhost:8080/health >/dev/null
TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"SmokePass123!"}' | node -e "let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>console.log(JSON.parse(d).token||''));")
[ -n "$TOKEN" ]
kill $PID
wait $PID 2>/dev/null || true
echo 'smoke test ok'
