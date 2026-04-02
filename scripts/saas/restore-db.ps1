Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath
)

if (-not (Test-Path $InputPath)) {
    throw "Arquivo de backup nao encontrado: $InputPath"
}

$composeDir = "C:\APIMENEGER\infra\compose"
Set-Location $composeDir

Get-Content $InputPath | docker compose --env-file .env.saas -f docker-compose.saas.yml exec -T postgres `
  sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"'

Write-Host "Restore concluido."
