Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$composeDir = "C:\APIMENEGER\infra\compose"
$backupDir = Join-Path $composeDir "backups"
New-Item -ItemType Directory -Force $backupDir | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFile = Join-Path $backupDir "atendecrm_saas_$timestamp.sql"

Set-Location $composeDir
docker compose --env-file .env.saas -f docker-compose.saas.yml exec -T postgres `
  sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | Out-File -Encoding utf8 $backupFile

Write-Host "Backup salvo em $backupFile"
