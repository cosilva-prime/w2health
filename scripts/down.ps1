# Para e remove os containers do W2Health Intelligence.
# Use -Volumes para apagar tambem o banco (volume pgdata).
param([switch]$Volumes)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
if ($Volumes) {
    docker compose down -v
} else {
    docker compose down
}
