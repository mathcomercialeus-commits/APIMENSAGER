Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$composeDir = "C:\APIMENEGER\infra\compose"
$envFile = Join-Path $composeDir ".env.saas"
$envExample = Join-Path $composeDir ".env.saas.example"

if (-not (Test-Path $envFile)) {
    Copy-Item $envExample $envFile
    Write-Host "Arquivo .env.saas criado a partir do exemplo. Revise as credenciais antes do primeiro uso."
}

Set-Location $composeDir
docker compose --env-file .env.saas -f docker-compose.saas.yml up -d --build
