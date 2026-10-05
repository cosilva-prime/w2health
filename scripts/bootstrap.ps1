# Catálogo de planos/features + usuários demonstrativos (senhas exibidas UMA vez).
# Rode depois do seed. Idempotente: contas existentes não são alteradas.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
docker compose exec backend python -m app.saas.cli bootstrap-demo
