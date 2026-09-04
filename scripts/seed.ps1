# Gera a massa sintética dentro do container backend.
# Uso:  ./scripts/seed.ps1            (20.000 beneficiários)
#       ./scripts/seed.ps1 -Full      (100.000 beneficiários)
#       ./scripts/seed.ps1 -Beneficiarios 50000 -Seed 7
param(
    [switch]$Full,
    [int]$Beneficiarios = 20000,
    [int]$Seed = 42
)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
if ($Full) { $Beneficiarios = 100000 }
docker compose exec backend python -m app.seed.run --beneficiarios $Beneficiarios --seed $Seed
