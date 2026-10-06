# Fase 3 — Production Readiness / Hardening

> Objetivo: fechar os P0 **técnicos** que impediam o primeiro cliente real, sem criar
> funcionalidade nova de Healthcare Intelligence. Baseline: [PHASE3_BASELINE.md](PHASE3_BASELINE.md).

## Classificação final: **PILOT READY** (não PRODUCTION READY)

**Por quê não PRODUCTION READY:** continuam abertos P0 que não são de código — plataforma de
produção não provisionada (TLS real, rede, WAF), backup de produção/PITR inexistente, bucket e
gerenciador de segredos reais inexistentes, alertas não configurados, pentest externo não
realizado, DPA/LGPD jurídico pendente ([PRODUCTION_RELEASE_CHECKLIST.md](PRODUCTION_RELEASE_CHECKLIST.md)
tem FAIL em itens P0).

**Por quê PILOT READY:** todos os P0 **da aplicação** foram fechados com evidência — runtime
sem vulnerabilidade conhecida, carga assíncrona com worker isolado e recuperável, object
storage abstraído com adapter S3 testado contra MinIO real, configuração fail-closed,
containers não-root, restauração por tenant, observabilidade e CI. O deployment de referência
subiu "como produção" (TLS, migrations separadas, papéis distintos, S3, worker) e processou
carga real. Um **piloto controlado** (uma operadora, dados pseudonimizados, sob acordo
explícito) é tecnicamente viável **desde que** o ambiente do piloto cumpra o mínimo:
TLS real no proxy, banco com backup diário + PITR, bucket privado e cifrado, segredos fora do
servidor de aplicação, alertas de health/fila/erros, DPA assinado.

## O que mudou (resumo)

| Área | Antes | Depois |
|---|---|---|
| Dependências | Next 14 crítico; Starlette/cryptography vulneráveis | runtime com zero achados ([DEPENDENCY_SECURITY.md](DEPENDENCY_SECURITY.md)) |
| Carga | síncrona na requisição | fila PostgreSQL + worker; retry/backoff, lease renovado, reaper, dead jobs, retry/cancel auditados ([WORKER_AND_QUEUE.md](WORKER_AND_QUEUE.md)) |
| RAW | filesystem local | `ObjectStorage` + adapter S3-compatível ([OBJECT_STORAGE.md](OBJECT_STORAGE.md)) |
| Configuração | 3 checagens em produção | ambientes formais; 15+ regras fail-closed (API e worker); segredos por arquivo |
| Containers | root, com pytest/ruff, migrations no start | multi-stage, uid 10001, runtime enxuto, migrations em job separado |
| Proxy | `TRUST_PROXY_HEADERS` lia XFF de qualquer origem | IP só de `FORWARDED_ALLOW_IPS`; Trusted Hosts; HSTS/CSP |
| Observabilidade | logs JSON básicos, `/api/health` | campos padronizados, log de acesso com duração, `/metrics`, `/health/live`, `/health/ready`, heartbeat do worker |
| Upload | tamanho/quantidade | + MIME, binário, colunas, bytes/linha, linhas, rate limit por usuário |
| Backup | dump/restore local | + procedimento formal, restauração por tenant testada |
| Frontend | sem headers de segurança | CSP, X-Frame, nosniff, COOP, Permissions-Policy, HSTS opcional; tela de fila/jobs |
| CI | inexistente | backend, frontend, imagens |

## Testes

| | Antes (baseline) | Depois |
|---|---|---|
| Backend (`pytest`) | 306 | **419 — todos passando** (5 min 58 s; inclui os testes S3 contra MinIO real) |
| Novos nesta fase | — | `test_worker` (18), `test_object_storage` (46, inclui MinIO real), `test_phase3_security` (45), `test_tenant_backup` (4), ajustes em 4 testes existentes (ver abaixo) |
| E2E navegador | Fase 2 17/17, recovery 6/6 | Fase 2 17/17, recovery 6/6, **Fase 3 10/10** (upload assíncrono, fila, zero violação de CSP), smoke Fase 1 OK até MFA obrigatório (desligado no `.env` local por decisão do usuário) |

Testes existentes ajustados (nenhuma proteção removida): `test_producao_exige_segredos` (agora
verifica os 3 problemas originais como subconjunto, porque há mais regras);
`test_rotas_de_dados_exigem_autenticacao` (health de liveness/readiness é público por desenho);
`test_lista_de_tabelas_da_migration_bate_com_metadata` (inclui as tabelas novas);
`test_pipeline_context_carrega_ids_de_correlacao` (inclui `job_id`). O helper de upload dos
testes da Fase 2 passou a drenar a fila com o worker real — nenhuma asserção mudou.

## Provas repetidas da Fase 2 (agora via fila/worker)

* **Generic CSV**: `test_pipeline_e2e` (24) passa pelo upload → 202 → worker → mesmos valores
  de despesa/receita calculados direto do arquivo; E2E de navegador da Fase 2 17/17.
* **Synthetic**: bancos de teste semeados pelo gerador; `test_caminho_sintetico_tem_a_mesma_linhagem`;
  tenant `w2h-demo` servindo os endpoints no baseline de performance.
* **Multi-tenant concorrente**: `test_cargas_concorrentes_a_b_isoladas_e_processadas_uma_vez`
  (3 workers, A e B com os mesmos `BEN-…`), `test_worker_nao_vaza_contexto_entre_tenants_a_b_a`,
  `test_mesmos_ids_de_negocio_nos_dois_tenants_sem_colisao` — zero vazamento.

## Documentos da fase
[PHASE3_BASELINE](PHASE3_BASELINE.md) · [WORKER_AND_QUEUE](WORKER_AND_QUEUE.md) ·
[OBJECT_STORAGE](OBJECT_STORAGE.md) · [PRODUCTION_DEPLOYMENT](PRODUCTION_DEPLOYMENT.md) ·
[PRODUCTION_RELEASE_CHECKLIST](PRODUCTION_RELEASE_CHECKLIST.md) · [PENTEST_READINESS](PENTEST_READINESS.md) ·
[LGPD_TECHNICAL_CONTROLS](LGPD_TECHNICAL_CONTROLS.md) · [INCIDENT_RESPONSE](INCIDENT_RESPONSE.md) ·
[OPERATIONS_RUNBOOK](OPERATIONS_RUNBOOK.md) · [PERFORMANCE_BASELINE](PERFORMANCE_BASELINE.md) ·
atualizados: DEPENDENCY_SECURITY, BACKUP_AND_RECOVERY, SECURITY_AND_TENANT_ISOLATION,
THREAT_MODEL_V1, PIPELINE_ARCHITECTURE, RAW_STORAGE, INGESTION_FRAMEWORK, PHASE2_DATA_PLATFORM,
CLIENT_ONBOARDING, V1_ROADMAP.

## Dívidas técnicas registradas
Gold reconstruída por inteiro na janela do tenant (114 s / 59 mil eventos); CSP com
`'unsafe-inline'`; Tailwind 3 (advisories de build sem correção na linha); `next-env.d.ts`
gerado; testes de S3 dependem de endpoint (`S3_TEST_ENDPOINT`) — no CI rodam só os de
contrato com cliente falso; retenção/eliminação por tenant manual; papel dono superusuário na
referência; o `httpx` usado pelo `TestClient` está depreciado pelo Starlette 1.x (aviso, sem
impacto); volumes antigos criados como root exigem `chown` no upgrade.
