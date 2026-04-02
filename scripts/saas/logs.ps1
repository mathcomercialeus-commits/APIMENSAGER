Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

param(
    [string]$Service = ""
)

$composeDir = "C:\APIMENEGER\infra\compose"
Set-Location $composeDir

if ($Service) {
    docker compose --env-file .env.saas -f docker-compose.saas.yml logs -f $Service
} else {
    docker compose --env-file .env.saas -f docker-compose.saas.yml logs -f
}
