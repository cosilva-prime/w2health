# Runbook de operação — W2Health

Procedimentos para quem está de plantão. Comandos assumem o deployment de referência
(`docker compose -p w2h-prod -f docker-compose.production.example.yml`, abreviado `dc`);
em outra plataforma o equivalente é o mesmo (reiniciar serviço, ler logs, executar comando
no contêiner). Logs são JSON: filtre por `service`, `event`, `tenant_id`, `job_id`,
`request_id`. **Nunca** cole segredo, token ou dado de beneficiário em ticket/chat.

## Sinais principais

| Sinal | Onde | Alerta sugerido (hipótese inicial, calibrar com a operação) |
|---|---|---|
| API viva / pronta | `GET /health/live`, `GET /health/ready` | ready ≠ 200 por 2 min |
| Taxa de erro | `w2h_http_requests_total{status="5xx"}` | > 2 % em 5 min |
| Latência | `w2h_http_request_duration_seconds` | p95 > 3 s em 10 min (rotas analíticas) |
| Fila | `w2h_queue_depth`, `w2h_queue_oldest_seconds` | job na fila há > 15 min |
| Workers | `w2h_workers_alive` | 0 por 2 min |
| Travados | `w2h_jobs_stuck` | > 0 |
| Falhas de carga | `w2h_pipeline_failures_total{reason}` | qualquer `reconciliation_failed`; `infrastructure` crescendo |
| Banco | métricas do provedor | conexões > 80 %, replicação/backup falhando, disco > 80 % |
| Storage | métricas do provedor | erros 5xx, bucket inacessível |

## 1. API fora do ar
1. `dc ps api`; `dc logs --tail 200 api`. Erro `Configuração de segurança inválida` = segredo/
   variável faltando ou insegura (fail-closed) → corrigir a configuração, não desligar a validação.
2. `/health/ready` mostra qual dependência está `fail` (`database`, `pipeline_database`, `object_storage`).
3. Reiniciar: `dc restart api`. Se o problema começou num deploy → rollback da imagem (migrations
   são aditivas; a versão anterior roda no esquema novo).

## 2. Worker fora do ar
1. `dc ps worker` (healthcheck = heartbeat do loop); `dc logs --tail 200 worker`.
2. Jobs não se perdem: ficam `QUEUED`; jobs que estavam `RUNNING` são devolvidos à fila pelo
   reaper quando o lease vence (padrão 10 min).
3. `dc restart worker`. Para drenar manualmente: `dc run --rm worker python -m app.worker drain`.

## 3. Fila parada (job antigo em QUEUED)
1. `w2h_workers_alive` = 0 → item 2. Workers vivos e fila parada → ver `next_attempt_at` no
   Admin (pode ser backoff de retry).
2. Admin → Integrações → Fila: status, tentativas e último erro (mensagem segura).

## 4. Banco indisponível
* API: `/health/ready` = `database: fail`, respostas 5xx. Worker: recua com backoff, jobs em
  andamento viram retry (`banco de dados indisponível`) — sem perda.
* Ações: status do serviço gerenciado; conexões esgotadas (`max_connections`); disco.
* Ao voltar: a fila retoma sozinha; conferir `w2h_jobs{status="FAILED"}` com motivo
  `infrastructure` e reexecutar pelo Admin se as tentativas se esgotaram.

## 5. Object storage indisponível
* Upload → 503 "Armazenamento indisponível" (nada enfileirado — o cliente reenvia).
* Worker → retry com backoff; esgotado → FAILED `infrastructure`, reexecutável pelo Admin.
* `python -m app.ops.storage_init` confere bucket/credencial.

## 6. Pipeline travado
* `w2h_jobs_stuck > 0` ou Admin mostra "travado" (RUNNING com lease vencido).
* O reaper recupera automaticamente (reenfileira ou falha se sem tentativas). Para acelerar:
  Admin → Reexecutar (auditado). Nunca editar `pipeline_jobs` à mão em produção.

## 7. Taxa de erro alta
1. Filtrar logs `event=http.request status>=500` por `route`; correlacionar por `request_id`.
2. Erro 500 genérico ao usuário + `request_id`; o stack trace fica só no log do servidor.
3. Picos de 429: limitador de login/upload funcionando (verificar se é ataque ou cliente legítimo).

## 8. Falha de Data Quality
* Ingestão `FAILED`, motivo `dq_blocked`; Admin → Detalhes → Data Quality mostra regra, linha
  e motivo (sem conteúdo clínico).
* Não reexecutar: corrigir o mapping (nova versão) ou pedir arquivo corrigido ao cliente e
  reenviar. Mudar `max_rejected_ratio` só com decisão registrada no onboarding.

## 9. Falha de reconciliação
* `reconciliation_failed`: nada foi publicado (rollback). Detalhes mostram verificação,
  esperado × obtido. Tratar como possível bug ou dado inconsistente — abrir incidente se
  ocorrer em carga já homologada ([INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md)).

## 10. Restauração
* **Banco inteiro (DR)**: restore do snapshot/PITR do provedor → `alembic current` → subir API/worker.
* **Um tenant**: `python -m app.ops.tenant_backup verify --file X` → `import --file X --tenant T
  --confirmar T` (transação única; não toca outros tenants; revoga sessões do tenant) —
  [BACKUP_AND_RECOVERY.md](BACKUP_AND_RECOVERY.md) §3.

## 11. Suspensão de tenant
Admin → Tenants → Suspender (auditado). Efeito: login e tokens do tenant bloqueados na hora
(status relido a cada requisição). Cargas de homologação continuam possíveis em SUSPENDED;
INACTIVE não recebe carga. Reativar pelo mesmo caminho.

## 12. Rotação de credenciais
| Segredo | Procedimento | Impacto |
|---|---|---|
| `JWT_SECRET_KEY` | trocar arquivo/segredo → restart API | todas as sessões caem (re-login) |
| `DATA_ENCRYPTION_KEY` | adicionar a nova chave **à frente** (`nova,antiga`) → restart → recifrar (rotação de segredos do tenant via Admin) → remover a antiga | nenhum, se feito nessa ordem |
| Senha `w2health_app` / `w2health_pipeline` | `ALTER ROLE ... PASSWORD` → atualizar `DATABASE_URL`/`DATABASE_PIPELINE_URL` → restart api/worker | reconexão |
| Credencial do object storage | criar nova chave no provedor → atualizar segredo → restart → revogar a antiga | nenhum |
| `METRICS_TOKEN` | trocar no segredo e no coletor | coleta interrompida até atualizar o coletor |
| Credencial de integração de um tenant | Admin → Tenants → Segredos (rotacionar) | próxima carga usa a nova |

## 13. Upgrade
Ver [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md) §7 (inclui a nota de `chown` de volumes
criados por imagens antigas que rodavam como root).
