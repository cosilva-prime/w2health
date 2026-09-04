# Sobe todo o ambiente W2Health Intelligence (build + start em background).
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
docker compose up -d --build
docker compose ps
Write-Host ""
Write-Host "Frontend:  http://localhost:3000"
Write-Host "Backend:   http://localhost:8010/api/health"
Write-Host "Swagger:   http://localhost:8010/docs"
