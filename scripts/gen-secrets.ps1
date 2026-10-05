# Gera um .env local com segredos aleatórios (JWT, criptografia, senha do papel de runtime).
# Não sobrescreve um .env existente. Os valores nunca devem ir para o repositório.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
if (Test-Path ".env") {
    Write-Host ".env já existe — nada foi alterado. Apague-o manualmente se quiser regenerar."
    exit 0
}
$py = if (Test-Path "backend/.venv/Scripts/python.exe") { "backend/.venv/Scripts/python.exe" } else { "python" }
$jwt = & $py -c "import secrets;print(secrets.token_urlsafe(48))"
$fernet = & $py -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"
$appdb = & $py -c "import secrets;print(secrets.token_urlsafe(18))"
$pipedb = & $py -c "import secrets;print(secrets.token_urlsafe(18))"
(Get-Content ".env.example") `
    -replace '^APP_DB_PASSWORD=.*$', "APP_DB_PASSWORD=$appdb" `
    -replace '^PIPELINE_DB_PASSWORD=.*$', "PIPELINE_DB_PASSWORD=$pipedb" `
    -replace '^JWT_SECRET_KEY=.*$', "JWT_SECRET_KEY=$jwt" `
    -replace '^DATA_ENCRYPTION_KEY=.*$', "DATA_ENCRYPTION_KEY=$fernet" |
    Set-Content -Encoding utf8 ".env"
Write-Host ".env criado com segredos aleatórios."
