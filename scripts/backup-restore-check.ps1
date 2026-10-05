# Teste de backup/restore (ambiente LOCAL/Docker Compose). NÃO é backup de produção.
#
# 1. pg_dump (formato custom) do banco principal — somente leitura;
# 2. restore num banco TEMPORÁRIO (w2health_restore_check), nunca no principal;
# 3. compara contagens por tabela e por tenant entre origem e restaurado;
# 4. empacota o volume RAW (tar.gz) e confere a lista de arquivos;
# 5. remove o banco temporário. Artefatos ficam em var/backups/ (gitignored).
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$pgUser = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "w2health" }
$pgDb = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "w2health" }
$tmpDb = "w2health_restore_check"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outDir = "var/backups"
New-Item -ItemType Directory -Force $outDir | Out-Null

function Psql([string]$db, [string]$sql) {
    $r = docker compose exec -T postgres psql -U $pgUser -d $db -At -v ON_ERROR_STOP=1 -c $sql
    if ($LASTEXITCODE -ne 0) { throw "psql falhou em $db" }
    return $r
}

# tabelas do data plane (com tenant_id) + controle
$porTenant = @("beneficiarios", "contratos", "prestadores", "planos", "eventos_assistenciais", "receitas",
    "agg_sinistralidade_competencia", "source_connections", "ingestion_runs", "raw_objects",
    "data_quality_results", "reconciliation_results", "capability_readiness", "audit_logs")
$globais = @("tenants", "users", "user_tenants", "plans", "features", "alembic_version")

function Contagens([string]$db) {
    $partes = @()
    foreach ($t in $porTenant) {
        $partes += "SELECT '$t' AS tabela, coalesce(tenant_id::text, '-') AS tenant, count(*) AS n FROM $t GROUP BY 2"
    }
    foreach ($t in $globais) { $partes += "SELECT '$t', '-', count(*) FROM $t" }
    $sql = "SELECT tabela || '|' || tenant || '|' || n FROM (" + ($partes -join " UNION ALL ") + ") x ORDER BY 1"
    return (Psql $db $sql) -join "`n"
}

Write-Host "== 1. pg_dump de '$pgDb' =="
$dumpName = "w2health_$stamp.dump"
docker compose exec -T postgres pg_dump -U $pgUser -d $pgDb -Fc -f "/tmp/$dumpName"
if ($LASTEXITCODE -ne 0) { throw "pg_dump falhou" }
docker compose cp "postgres:/tmp/$dumpName" "$outDir/$dumpName" | Out-Null
$tam = [math]::Round((Get-Item "$outDir/$dumpName").Length / 1MB, 1)
Write-Host "dump: $outDir/$dumpName ($tam MB)"

Write-Host "== 2. restore em '$tmpDb' (temporário) =="
Psql "postgres" "DROP DATABASE IF EXISTS $tmpDb" | Out-Null
Psql "postgres" "CREATE DATABASE $tmpDb" | Out-Null
$inicio = Get-Date
docker compose exec -T postgres pg_restore -U $pgUser -d $tmpDb --no-owner --role=$pgUser "/tmp/$dumpName"
if ($LASTEXITCODE -ne 0) { throw "pg_restore falhou" }
$dur = [math]::Round(((Get-Date) - $inicio).TotalSeconds, 1)
Write-Host "restore em $dur s"

Write-Host "== 3. contagens origem × restaurado =="
$a = Contagens $pgDb
$b = Contagens $tmpDb
$ok = ($a -eq $b)
$a | Set-Content -Encoding utf8 "$outDir/counts_$stamp.txt"
$linhas = ($a -split "`n").Count
Write-Host "$linhas linhas (tabela|tenant|n) comparadas: $(if ($ok) { 'IGUAIS' } else { 'DIFERENTES' })"
$rls = Psql $tmpDb "SELECT count(*) FROM pg_class WHERE relrowsecurity AND relforcerowsecurity"
Write-Host "tabelas com RLS (ENABLE+FORCE) no restaurado: $rls"

Write-Host "== 4. volume RAW =="
$rawTar = "$outDir/raw_$stamp.tar.gz"
docker compose exec -T backend tar czf /tmp/raw.tgz -C /var/lib/w2health/raw .
docker compose cp "backend:/tmp/raw.tgz" $rawTar | Out-Null
$arquivosRaw = (docker compose exec -T backend sh -c "find /var/lib/w2health/raw -type f | wc -l").Trim()
$noTar = (tar tzf $rawTar | Where-Object { -not $_.EndsWith("/") }).Count
Write-Host "RAW: $arquivosRaw arquivos no volume, $noTar no pacote ($rawTar)"
$okRaw = ([int]$arquivosRaw -eq [int]$noTar)

Write-Host "== 5. limpeza =="
Psql "postgres" "DROP DATABASE $tmpDb" | Out-Null
docker compose exec -T postgres rm -f "/tmp/$dumpName"
docker compose exec -T backend rm -f /tmp/raw.tgz
Write-Host "banco temporário removido; artefatos em $outDir/"

if ($ok -and $okRaw) { Write-Host "RESULTADO: PASS"; exit 0 }
Write-Host "RESULTADO: FAIL"
exit 1
