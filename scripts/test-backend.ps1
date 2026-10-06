# Roda a suite de testes do backend dentro de um container efemero.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
docker compose --profile test run --rm --build backend-test
