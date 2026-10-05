# Roadmap V1 — W2Health

> Situação após a **Fase 2 — Fundação Operacional de Integração**. Itens de DISCOVERY
> **não** são movidos para implementação sem decisão explícita.

## Concluído na Fase 2

| Item (era P0/P1) | Onde |
|---|---|
| Papel de banco separado para pipelines, sob RLS, tenant obrigatório | `w2health_pipeline` — [PIPELINE_ARCHITECTURE.md](PIPELINE_ARCHITECTURE.md) |
| Primeira fonte via Data Platform (arquivo → RAW → mapping → Silver → Gold), sem acoplar a API à origem | [PHASE2_DATA_PLATFORM.md](PHASE2_DATA_PLATFORM.md) |
| Auditoria de leitura de dado individual de beneficiário | `data.beneficiary.*` (sem conteúdo clínico) |
| Rate limit compartilhado entre réplicas | `RATE_LIMIT_BACKEND=database` (chaves com hash; Redis não exigido) |
| Códigos de recuperação de MFA | hash, uso único, regeneração invalida os anteriores, auditado |
| Capability Readiness automatizada (contratada × dados prontos) | [CAPABILITY_READINESS.md](CAPABILITY_READINESS.md) |
| Logs estruturados com correlação por tenant/pipeline | `LOG_FORMAT=json` |
| Revisão de dependências (SCA) — processo e primeira rodada | [DEPENDENCY_SECURITY.md](DEPENDENCY_SECURITY.md) |
| Teste local de backup/restore (banco + RAW) | [BACKUP_AND_RECOVERY.md](BACKUP_AND_RECOVERY.md) |

## P0 — bloqueia cliente real

| Item | Por quê |
|---|---|
| **Upgrade de dependências com vulnerabilidade conhecida**: Next 14 → 15/16 (crítica), FastAPI/Starlette (multipart do upload), cryptography ≥ 50 | [DEPENDENCY_SECURITY.md](DEPENDENCY_SECURITY.md) — correções só em versão major |
| Infra de produção: TLS ponta a ponta, `COOKIE_SECURE=true`, proxy com limite de corpo, banco gerenciado com cifragem em repouso, segredos em cofre (KMS/Key Vault), domínio próprio | dado de saúde (LGPD art. 11) |
| Adapter de RAW em object storage (S3/ADLS/GCS/MinIO) com cifragem e acesso restrito | hoje o RAW é filesystem/volume local |
| Backup de produção cifrado com PITR, restauração **por tenant** automatizada e testada periodicamente; retenção/eliminação por tenant | não existe backup de produção |
| Imagem de runtime sem dependências de dev (pytest/ruff) | superfície de ataque |
| Execução de carga fora da requisição HTTP (fila/worker) para pacotes grandes | upload hoje é síncrono (limite 50 MB/arquivo) |
| Pentest externo | validação independente |
| Processo de onboarding jurídico (DPA, termo de uso, encarregado/DPO, procedimento de incidente) | LGPD |

## P1 — V1 comercial

| Item |
|---|
| Primeiro conector DATABASE ou API (o cadastro já aceita o tipo e a referência de segredo; falta a extração) |
| Agendamento de cargas recorrentes por fonte |
| Carga incremental (watermark/CDC) — hoje: UPSERT de dimensões e snapshot por competência |
| Convite de usuário por e-mail com link de uso único (hoje: senha temporária exibida uma vez) |
| SSO (OIDC/SAML) por tenant |
| Listar e encerrar sessões ativas na conta; alerta de novo dispositivo |
| FK `tenant_id → tenants.id` no data plane (após revisar teste histórico e janela de lock) |
| Readiness com frescor e cobertura (ex.: "última competência há > 2 meses") |
| Tela de Data Quality para o **cliente** (hoje só no Admin Works2Data) |
| Exportações (CSV/PDF) com auditoria e marca d'água de tenant — **não** criadas nesta fase |
| Métricas por tenant e alertas operacionais (falha de carga, reconciliação FAIL) |
| Lint herdado (17 achados de ruff em arquivos anteriores à Fase 2) |
| Revisão da cor do delta de sinistralidade no card executivo (herdado do MVP) |
| `?id_contrato=` documentado na v1.2 para a lista de beneficiários: a rota lê `contrato_id` (alinhar doc/rota) |
| Faixa etária por competência (herdado do MVP) |

## P2 — pós-V1

| Item |
|---|
| Schema/banco dedicado para clientes que exijam isolamento físico (estratégias B/C de MULTI_TENANCY) |
| Histórico de dimensões (SCD2) e linhagem por versão |
| Billing/medição de uso por tenant |
| Preferências por usuário (dashboards salvos, filtros favoritos) |
| Internacionalização da interface |
| Tema escuro |

## DISCOVERY — ainda não implementar

Reajuste contratual (motor de simulação) · receita por contrato e sinistralidade
contratual · receita atribuída por beneficiário / "sinistralidade individual" · previsão,
ML e projeções · LLM/chatbot de narrativa · conectores específicos MV/Tasy/Benner/Datasul/TISS ·
Data Lake físico, Kafka, Kubernetes, microserviços, Airflow, Spark, Data Mesh ·
funcionalidades clínicas.
Referências: [DISCOVERY_GESTAO_SAUDE.md](DISCOVERY_GESTAO_SAUDE.md),
[EVOLUCAO_FEEDBACK_ESPECIALISTA.md](EVOLUCAO_FEEDBACK_ESPECIALISTA.md).
