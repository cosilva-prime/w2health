# Checklist de release de produção — W2Health

> Gate para colocar um cliente real em produção. Preenchido em **2026-10-06** para o estado
> da branch `fase3-production-readiness`, **sem ambiente de produção provisionado**.
> PASS = verificado com evidência · FAIL = não atendido · N/A = não se aplica.
> Regra: qualquer FAIL em item marcado **P0** bloqueia produção.

## APPLICATION
| Item | P0 | Status | Evidência |
|---|---|---|---|
| Suíte backend verde | ✓ | PASS | `pytest` — ver [PHASE3_PRODUCTION_READINESS.md](PHASE3_PRODUCTION_READINESS.md) §Testes |
| Typecheck, lint e build do frontend | ✓ | PASS | `tsc`, ESLint, `next build` (CI `frontend`) |
| Testes de navegador (fluxos críticos) | ✓ | PASS | E2E Fase 1 smoke, Fase 2 17/17, recovery 6/6, Fase 3 10/10 |
| Pipeline assíncrono (API não processa carga) | ✓ | PASS | `test_upload_responde_rapido_*`; upload 1–3 s, processamento no worker |
| Generic CSV → mesmos indicadores | ✓ | PASS | `test_pipeline_e2e` (24) via fila/worker |
| Synthetic generator continua funcionando |  | PASS | seed dos bancos de teste; `test_caminho_sintetico_tem_a_mesma_linhagem` |
| Configuração fail-closed | ✓ | PASS | `test_producao_fail_closed_*`; validado no deployment de referência |

## DATABASE
| Item | P0 | Status | Evidência |
|---|---|---|---|
| Migrations aplicam do zero e a partir da Fase 2 | ✓ | PASS | job `migrate` em banco vazio; cópia do banco da Fase 2 (upgrade/downgrade/upgrade, `alembic check` limpo) |
| Papéis separados (dono / runtime / pipeline), sem SUPERUSER/BYPASSRLS | ✓ | PASS | `test_papeis_de_runtime_e_pipeline_com_menor_privilegio` |
| RLS ENABLE+FORCE em todo o data plane (27 tabelas) | ✓ | PASS | `test_rls` |
| Papel dono não-superusuário em banco gerenciado | ✓ | FAIL | na referência o dono é o superusuário do contêiner Postgres; definir no provisionamento |
| Banco gerenciado com cifragem em repouso | ✓ | FAIL | plataforma não provisionada |

## SECURITY
| Item | P0 | Status | Evidência |
|---|---|---|---|
| Zero vulnerabilidade conhecida no runtime | ✓ | PASS | pip-audit runtime/dev; `npm audit --omit=dev` = 0 |
| Ferramentas de build com advisories aceitos e documentados |  | PASS | [DEPENDENCY_SECURITY.md](DEPENDENCY_SECURITY.md) §3 |
| Testes de segurança (15 cenários críticos) | ✓ | PASS | `test_phase3_security.py` (mapa no cabeçalho) |
| Headers (API e frontend), CSP sem violação | ✓ | PASS | testes + E2E Fase 3 |
| CORS restrito, Trusted Hosts, proxy confiável | ✓ | PASS | testes + referência |
| Upload endurecido e limitado | ✓ | PASS | `test_upload_*` |
| MFA obrigatório para plataforma; recovery codes | ✓ | PASS | `test_mfa`, `test_phase2_security` |
| Pentest externo realizado e achados tratados | ✓ | FAIL | não realizado — escopo pronto em [PENTEST_READINESS.md](PENTEST_READINESS.md) |
| Scan de imagens no registro |  | FAIL | P1 |

## INFRA
| Item | P0 | Status | Evidência |
|---|---|---|---|
| Containers não-root, runtime sem ferramentas de dev | ✓ | PASS | CI `images`; inspeção local (uid 10001) |
| Arquitetura TLS/proxy documentada e validada em referência | ✓ | PASS | [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md) §8 |
| Plataforma de produção provisionada (rede privada, TLS real, WAF/LB) | ✓ | FAIL | nuvem/região não escolhidas |
| Gerenciador de segredos real | ✓ | FAIL | referência usa arquivos locais |
| Object storage de produção privado/cifrado/versionado | ✓ | FAIL | adapter pronto (S3); bucket não provisionado |

## BACKUP
| Item | P0 | Status | Evidência |
|---|---|---|---|
| Procedimento formal (DR × tenant, RPO/RTO hipótese) | ✓ | PASS | [BACKUP_AND_RECOVERY.md](BACKUP_AND_RECOVERY.md) |
| Restauração local testada (banco + RAW) |  | PASS | `backup-restore-check` 2026-10-06 |
| Restauração por tenant testada | ✓ | PASS | `test_tenant_backup` + referência com S3 |
| Backup automático de produção + PITR + teste periódico | ✓ | FAIL | depende da plataforma |

## OBSERVABILITY
| Item | P0 | Status | Evidência |
|---|---|---|---|
| Logs JSON padronizados sem segredo/PII | ✓ | PASS | `test_log_*`, `test_segredo_nunca_aparece_*` |
| Métricas HTTP / fila / pipeline | ✓ | PASS | `/metrics` (`test_metrics_*`) |
| Health live/ready (API) e healthcheck do worker | ✓ | PASS | `test_health_*`, compose |
| Coleta, dashboards e alertas configurados | ✓ | FAIL | ferramenta não escolhida; alertas propostos no runbook |

## DATA PLATFORM
| Item | P0 | Status | Evidência |
|---|---|---|---|
| Worker com retry, lease, reaper, dead jobs, admin retry/cancel | ✓ | PASS | `test_worker` (18) |
| Isolamento do worker (A→B→A, concorrência, job adulterado) | ✓ | PASS | `test_worker` |
| Idempotência (pacote, job, reexecução) | ✓ | PASS | `test_pipeline_e2e`, `test_worker` |
| DQ e reconciliação bloqueiam publicação | ✓ | PASS | `test_dq_*`, `test_reconciliacao_fail_nao_publica` |
| Performance baseline registrado |  | PASS | [PERFORMANCE_BASELINE.md](PERFORMANCE_BASELINE.md) |

## LGPD
| Item | P0 | Status | Evidência |
|---|---|---|---|
| Controles técnicos mapeados | ✓ | PASS | [LGPD_TECHNICAL_CONTROLS.md](LGPD_TECHNICAL_CONTROLS.md) |
| Minimização / pseudonimização / segregação / auditoria de acesso | ✓ | PASS | idem + testes |
| Retenção e eliminação automatizadas |  | FAIL | P1 (procedimento manual documentado) |
| DPA, base legal, DPO, suboperadores, residência de dados | ✓ | FAIL | jurídico / decisão de deployment |

## OPERATIONS
| Item | P0 | Status | Evidência |
|---|---|---|---|
| Runbook | ✓ | PASS | [OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md) |
| Resposta a incidentes | ✓ | PASS | [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) (prazos legais com o jurídico) |
| Plantão definido / responsáveis nomeados | ✓ | FAIL | organizacional |
| CI executando em cada push |  | PASS | `.github/workflows/ci.yml` (validar a primeira execução no GitHub) |

## CLIENT ONBOARDING
| Item | P0 | Status | Evidência |
|---|---|---|---|
| Discovery, requisitos de dados, mapping, homologação, reconciliação | ✓ | PASS | [CLIENT_ONBOARDING.md](CLIENT_ONBOARDING.md) (20 passos) |
| Pacote do cliente real recebido e homologado | ✓ | N/A | próxima fase |
