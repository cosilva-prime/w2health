# Verificação de dependências (somente leitura): vulnerabilidades conhecidas no backend
# (pip-audit sobre o requirements.txt travado) e no frontend (npm audit, produção e total).
# NÃO atualiza nada automaticamente — upgrades major são decididos e testados à parte
# (ver docs/DEPENDENCY_SECURITY.md). Sai com código 1 se houver achado.
$ErrorActionPreference = "Continue"
Set-Location (Join-Path $PSScriptRoot "..")
$falhou = $false

Write-Host "== Backend: pip-audit (backend/requirements.txt) =="
if (Get-Command uvx -ErrorAction SilentlyContinue) {
    uvx pip-audit -r backend/requirements.txt --no-deps --disable-pip --progress-spinner off
    if ($LASTEXITCODE -ne 0) { $falhou = $true }
} else {
    Write-Host "uvx não encontrado — instale o uv (https://docs.astral.sh/uv/) ou rode: pip install pip-audit"
    $falhou = $true
}

Write-Host ""
Write-Host "== Frontend: npm audit (dependências de produção) =="
Push-Location frontend
npm audit --omit=dev
if ($LASTEXITCODE -ne 0) { $falhou = $true }
Write-Host ""
Write-Host "== Frontend: npm audit (inclui devDependencies — só build/lint; INFORMATIVO) =="
Write-Host "   Achados aqui não vão para o runtime; decisão registrada em docs/DEPENDENCY_SECURITY.md"
npm audit | Select-Object -Last 8
Pop-Location

if ($falhou) {
    Write-Host ""
    Write-Host "Há achados. Registre a análise/decisão em docs/DEPENDENCY_SECURITY.md (não rode 'npm audit fix --force')."
    exit 1
}
Write-Host "Sem vulnerabilidades conhecidas."
