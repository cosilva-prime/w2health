# Baseline de performance — W2Health (Fase 3)

> **Medição local, não é SLA.** Notebook Windows + Docker Desktop (WSL2), PostgreSQL 16 em
> contêiner, 1 worker, 1 processo uvicorn, sem tuning. Serve para comparar versões e
> dimensionar, não para prometer prazo a cliente.
>
> Reproduzir: `python scripts/perf_baseline.py --pacote <dir> --tenant perf-csv` (credenciais
> por variável de ambiente — ver o cabeçalho do script).

## 1. Pipeline (fonte FILE, assíncrono) — 2026-10-06

Pacote gerado por `generate_package.py --beneficiarios 5000 --meses 18 --seed 21`:
5,4 MB, 64.500 registros (5.000 beneficiários, 59.354 eventos, 72 receitas), tenant novo.

| Etapa | Tempo |
|---|---|
| Requisição de upload (validação + RAW + enfileirar) — **o que o usuário espera** | 3,1 s |
| `file_validation` (na requisição) | 2,5 s |
| `raw` (gravação, na requisição) | 0,2 s |
| `raw_read` (worker lê e confere sha256) | 1,1 s |
| `mapping` | 5,9 s |
| `data_quality` | 1,6 s |
| `silver` | 46,7 s |
| `gold` (`rebuild_aggregations` da janela do tenant) | **114,0 s** |
| `reconciliation` | 0,4 s |
| Job completo no worker | 170,3 s |
| Fim a fim (upload → SUCCESS) | 175,3 s |
| Reconciliação | PASS |

Pacote menor (300 beneficiários, 12 competências, 2.912 registros): upload enfileirado em
~1 s, job 3,5 s (E2E de navegador) e 33,9 s fim a fim no stack de produção de referência.

**Leitura:** a requisição ficou curta (o processamento saiu da HTTP). O gargalo é a
reconstrução da Gold (67 % do job), seguida da Silver. Otimização não foi feita nesta fase
(sem otimização prematura) — registrada como dívida P1 em [V1_ROADMAP.md](V1_ROADMAP.md):
Gold incremental por competência afetada. O lease do job é renovado em segundo plano, então
um passo longo não é confundido com worker morto.

## 2. Endpoints principais — 2026-10-06

Tenant sintético `w2h-demo` (20.000 beneficiários, 328.778 eventos, 24 competências),
competência 2026-06, 20 chamadas sequenciais após aquecimento, usuário MANAGER.

| Endpoint | p50 | p95 | máx |
|---|---|---|---|
| `GET /api/executive/overview` | 920 ms | 1.505 ms | 2.007 ms |
| `GET /api/analytics/sinistralidade` | 16 ms | 18 ms | 19 ms |
| `GET /api/analytics/sinistralidade/explain` (especialidade) | 160 ms | 246 ms | 261 ms |
| `GET /api/analytics/sinistralidade/composicao` | 18 ms | 23 ms | 34 ms |
| `GET /api/analytics/contratos` | 18 ms | 23 ms | 23 ms |
| `GET /api/analytics/prestadores` | 18 ms | 26 ms | 28 ms |
| `GET /api/analytics/prestadores/anomalias` | 186 ms | 320 ms | 329 ms |
| `GET /api/analytics/beneficiarios` | 52 ms | 261 ms | 423 ms |
| `GET /api/analytics/insights` | 724 ms | 1.269 ms | 1.355 ms |

Todos com status 200. Visão executiva e insights (que compõem várias análises) são os mais
lentos — candidatos a cache por (tenant, competência) se a operação real mostrar necessidade.

## 3. Outras medições

| Medição | Valor |
|---|---|
| Backup/restore local (dump 20,3 MB) — restore num banco temporário | 53 s |
| Suíte backend completa (419 testes) | ~6 min |
| Build das 3 imagens (sem cache) | ~10 min |
