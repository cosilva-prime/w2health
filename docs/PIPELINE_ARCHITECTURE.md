# Arquitetura do pipeline — W2Health (Fase 2)

Código: `backend/app/data_platform/` (orquestrador em `runner.py`). Visão geral e diagramas:
[PHASE2_DATA_PLATFORM.md](PHASE2_DATA_PLATFORM.md).

## 1. Princípios

1. **Tenant explícito, sempre.** Toda execução nasce de um `PipelineContext(tenant_id, …)`.
   Não existe "processar todos os tenants". Tenant inexistente ou suspenso → `PipelineError`.
2. **Papel próprio, sob RLS.** Pipelines usam `w2health_pipeline` (`DATABASE_PIPELINE_URL`):
   sem superusuário, sem `BYPASSRLS`, sem DDL. Sem essa URL o pipeline **não executa**
   (`PipelineDatabaseNotConfigured`) — não há fallback para o papel dono.
3. **Nada é promovido antes do gate de Data Quality.**
4. **Publicação atômica.** Silver + Gold + readiness + reconciliação numa única transação;
   reconciliação `FAIL` → rollback e nada muda para o usuário.
5. **Metadados sobrevivem à falha.** Ingestão, passos, DQ e reconciliação são gravados em
   transações próprias — "por que a carga do tenant X falhou?" sempre tem resposta.
6. **Estágio honesto.** Upload recebido não é "sucesso".
7. **Idempotência.** O mesmo pacote (mesmo checksum) não reprocessa nem duplica.
8. **Motor analítico agnóstico.** Endpoints e motor leem só tabelas canônicas/agg — o teste
   `test_motor_analitico_nao_conhece_a_origem` garante que `app/analytics` e
   `app/repositories` não referenciam `source_type`, `generic_csv`, `SYNTHETIC`,
   `ingestion_run`, `raw_objects` nem `data_platform` (exceção: `transparency.py`, que só
   exibe a procedência).

## 2. Papéis de banco

| Papel | Uso | Privilégios relevantes |
|---|---|---|
| `w2health` (dono) | migrations, CLI de bootstrap | DDL. Nunca usado pela API nem pelo pipeline |
| `w2health_app` | API | leitura do data plane; escrita em configuração, auditoria, sessões, `capability_readiness`, cadastro de fontes (`source_connections` INSERT/UPDATE) |
| `w2health_pipeline` | pipelines | SELECT/INSERT/UPDATE/DELETE no data plane e nos metadados de ingestão; INSERT em `audit_logs` (+ `SELECT (id, occurred_at)` para o `RETURNING`); nada de usuários/sessões/segredos |

Grants em `backend/app/db/rls.py` (`pipeline_grant_statements`) aplicados pela migration
`f4c5d6e7a8b9`. A senha do papel vem de `PIPELINE_DB_PASSWORD` (gerada por
`scripts/gen-secrets.ps1`; nunca versionada).

## 3. Etapas de uma execução (fonte FILE)

| # | Passo (`pipeline_runs.steps`) | O que faz | Estágio da ingestão ao final |
|---|---|---|---|
| 0 | `duplicate_check` | checksum do pacote = de uma ingestão já publicada? → `SUCCESS`, `duplicate_of`, nada reprocessado | `AVAILABLE` (duplicata) |
| 1 | `file_validation` | nome `<entidade>.csv`, extensão, tamanho, quantidade, UTF-8, CSV bem formado; nunca executa conteúdo | — |
| 2 | `raw` | grava os bytes originais no RAW (imutável) + `raw_objects` (sha256, linhas) | `RECEIVED` |
| 3 | `mapping` | aplica o mapping YAML versionado → linhas canônicas + rejeições com motivo | — |
| 4 | `data_quality` | regras + gate (`max_rejected_ratio`); `BLOCKED` encerra como `FAILED` | `VALIDATED` |
| 5 | `silver` | UPSERT de dimensões / SNAPSHOT por competência dos fatos, com linhagem | — (mesma transação) |
| 6 | `gold` | `rebuild_aggregations` restrito à janela de dados do tenant | `PROCESSED` |
| 7 | `reconciliation` | origem × Silver × Gold; `FAIL` → rollback | `RECONCILED` |
| 8 | publicação | commit; readiness recalculada; onboarding avança | `AVAILABLE` |

Status da ingestão: `PENDING → RUNNING → SUCCESS | PARTIAL | FAILED`. `PARTIAL` = publicada
com linhas rejeitadas dentro do limite configurado (`max_rejected_ratio` > 0). Reconciliação
`WARNING` publica e fica visível no resultado da reconciliação, sem mudar o status.

## 4. Transações

```
[tx meta 1]  ingestion_runs RUNNING + pipeline_runs        (commit)
[tx meta n]  passo concluído / DQ / estágio                 (commit a cada passo)
[tx dados]   Silver → Gold → readiness → reconciliação     (commit SÓ se tudo passar)
[tx meta]    resultado final + auditoria                    (commit)
```

Todas as sessões são do papel de pipeline e amarradas ao tenant (`bind_tenant` +
`after_begin` → `set_config('app.tenant_id', …)`).

## 5. Observabilidade

- Logs JSON (`LOG_FORMAT=json`) com `request_id`, `tenant_id`, `pipeline_run_id`,
  `ingestion_run_id`, `source_connection_id` via `contextvars` (`app/core/logging.py`).
  Chaves sensíveis (`password`, `token`, `secret`, `authorization`, …) saem `[REDACTED]`.
  Os logs de acesso do próprio uvicorn mantêm o formato dele (sem dado de negócio).
- Nenhum payload de linha (clínico) vai para log; DQ guarda só amostra de **referências**
  (linha do arquivo, `source_record_id`, motivo).
- Auditoria: `pipeline.ingestion_completed|failed|duplicate`,
  `integration.source_*`, `integration.onboarding_decision`.

## 6. Pontos de entrada

| Entrada | Quem | Observação |
|---|---|---|
| `POST /api/admin/tenants/{t}/sources/{id}/uploads` | SUPER_ADMIN | upload controlado (multipart `files`), executa em threadpool |
| `python -m app.data_platform.cli ingest --tenant … --source … --dir …` | operador | mesma função `run_file_ingestion` |
| `python -m app.seed.run` | DEV | Caminho A: registra a fonte SYNTHETIC e a ingestão com a mesma linhagem |

## 7. Limites conhecidos

Execução síncrona (sem fila/worker); sem agendamento; sem conectores DATABASE/API; RAW só em
filesystem local. Ver [PHASE2_DATA_PLATFORM.md](PHASE2_DATA_PLATFORM.md) §8.
