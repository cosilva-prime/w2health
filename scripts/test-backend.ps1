# Roda a suite de testes do backend dentro de um container efemero.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
docker compose run --rm --no-deps -v ./data_platform:/data_platform:ro backend pytest
