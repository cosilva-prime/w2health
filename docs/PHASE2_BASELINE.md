# Fase 2 — Baseline (antes da Fundação Operacional de Integração)

> **Data:** 2026-10-05 · **Branch:** `v1-saas-foundation` (commit `7119ce7`) ·
> **Alembic:** `e8b9c0d1f2a3` · Fonte de verdade da Fase 1: [V1_SAAS_FOUNDATION.md](V1_SAAS_FOUNDATION.md).
>
> Classificação: **IMPLEMENTADO** · **PARCIAL** · **DOCUMENTADO APENAS** · **AUSENTE**.

## 1. Execução do baseline

| Item | Resultado |
|---|---|
| Suíte backend (`pytest`) | **__TESTES__** |
| Typecheck frontend | ✅ |
| Docker Compose (postgres + backend + frontend) | ✅ em execução (migrations aplicadas no start) |
| Banco local | revisão `e8b9c0d1f2a3`; tenants `w2h-demo` (328.778 eventos) e `w2h-demo-b` (81.405 eventos) — ambos do gerador sintético |
| `source_connections` / `ingestion_runs` / `pipeline_runs` / `data_quality_results` | **0 linhas** (estrutura sem uso) |

## 2. Data Platform — estado por item

| Item | Estado | Evidência |
|---|---|---|
| Contratos canônicos (13 YAML) | **IMPLEMENTADO** (como documento) | `data_platform/contracts/*.yaml`, `docs/DATA_DICTIONARY.md` gerado |
| Mappings | **DOCUMENTADO APENAS** | `mappings/_template.yaml` e `exemplo_operadora_generica.yaml` usam `transformation` em texto livre (não executável) |
| Data Quality | **PARCIAL** | `quality/rules.py` executável e testado (evento, beneficiário, receita); nenhum pipeline o chama; `data_quality_results` vazia |
| SQL Silver/Gold/Serving | **DOCUMENTADO APENAS** | `data_platform/sql/*` referencia schemas `raw/silver/gold/serving` que **não existem**; não é executado |
| Gold (agregações) | **IMPLEMENTADO** | `backend/app/seed/aggregate.py::rebuild_aggregations` (tenant-scoped) — hoje acionado só pelo seed |
| Serving | **IMPLEMENTADO** (implícito) | API lê `agg_*` + tabelas canônicas no PostgreSQL da aplicação |
| Silver (modelo canônico físico) | **PARCIAL** | as tabelas `beneficiarios`, `eventos_assistenciais`, `planos`, `contratos`, `prestadores`, `procedimentos`, `especialidades`, `regioes`, `receitas` **são** o canônico físico, mas: sem metadados de linhagem (`source_system`, `ingestion_id`, `source_record_id`); `contratos` e `prestadores` **sem `codigo`** (o contrato canônico exige); colunas só do gerador obrigatórias |
| RAW | **AUSENTE** | nenhum armazenamento de dado original |
| Ingestão / conectores | **AUSENTE** | — |
| `source_connections` | **PARCIAL** | tabela com `source_system, tipo, config, ativo` — sem `name`, `status`, `secret_reference`, datas de execução |
| `ingestion_runs` / `pipeline_runs` | **PARCIAL** | estrutura sem `source_connection_id`, `checksum`, `triggered_by`, `error_summary`; status minúsculo |
| Idempotência | **DOCUMENTADO APENAS** | `INTEGRATION_GUIDE.md` §3 (sem implementação) |
| Lineage | **DOCUMENTADO APENAS** | metadados descritos, não persistidos |
| Reconciliação | **DOCUMENTADO APENAS** | `INTEGRATION_GUIDE.md` §6 |
| Capability Readiness | **DOCUMENTADO APENAS** | `CAPABILITY_READINESS.md`; hoje o acesso depende só de feature comercial |
| Onboarding | **DOCUMENTADO APENAS** | `CLIENT_ONBOARDING.md` (12 passos manuais) |
| Papel de banco para pipeline | **AUSENTE** | só `w2health_app` (runtime) e dono (`w2health`) — risco P0 registrado na Fase 1 |
| Cofre de segredos de integração | **IMPLEMENTADO** | `tenant_secrets` (Fernet, write-only) |

## 3. Application Platform — pendências herdadas da Fase 1

| Item | Estado |
|---|---|
| Auditoria de leitura de dado individual (beneficiário/eventos) | **AUSENTE** |
| Rate limit | **PARCIAL** — em memória do processo |
| MFA recovery codes | **AUSENTE** |
| Exportação de dados | **AUSENTE** (não existe no produto; não será criada) |
| Verificação de dependências | **AUSENTE** |
| Backup/restore | **DOCUMENTADO APENAS** (sem procedimento testado) |
| Logs estruturados / correlação | **PARCIAL** — `X-Request-ID` existe; logs em texto, sem contexto de tenant/pipeline |

## 4. Dependências diretas do gerador sintético

| Ponto | Tipo de dependência | Tratamento na Fase 2 |
|---|---|---|
| `contratos.vidas_alvo`, `prestadores.nivel_preco`, `procedimentos.custo_base/complexidade/tipo_atendimento_tipico/idade_*`, `planos.ticket_medio_base` | colunas NOT NULL que só o gerador sabe preencher | tornar anuláveis (fonte externa não fornece) |
| `contratos`/`prestadores` sem `codigo` | impede lookup por chave de negócio vindo de fonte externa | adicionar `codigo` (backfill nos dados sintéticos) |
| `agg_sinistralidade_competencia` gerada sobre **todo** o calendário global `competencias` | um tenant com janela menor ganharia meses vazios | Gold restrita à janela de dados do tenant |
| `insights._chave_pneumologia` busca a especialidade pelo código `PNEUMOLOGIA` do catálogo sintético | insight de sazonalidade respiratória só existe para esse catálogo | documentado; fonte externa sem esse código simplesmente não gera o insight (não quebra) |
| `seed_manifest` como "última atualização" | procedência | já cai para `ingestion_runs` quando existir |
| `cenarios_gabarito` / `cenario_tag` | QA sintético | já restrito a tenants sintéticos |
| `faixa_etaria` gravada na carga (idade na 1ª competência) | aproximação herdada do MVP | mesma regra aplicada à fonte externa (idade na 1ª competência carregada) |

## 5. Tabelas que alimentam o analytics (Serving atual)

`agg_sinistralidade_competencia`, `agg_competencia_dimensao`, `agg_prestador_competencia`,
`agg_beneficiario_competencia`, `agg_contrato_competencia` (Gold) e as canônicas
`beneficiarios`, `eventos_assistenciais`, `contratos`, `planos`, `prestadores`,
`procedimentos`, `especialidades`, `regioes`, `receitas` (detalhes, escopo de contrato,
coortes, catálogos). Nenhuma rota lê RAW.

## 6. Decisões para a Fase 2 (a partir deste baseline)

1. **Silver físico = as tabelas canônicas existentes** (o mesmo lugar onde o gerador
   escreve). Criar um schema `silver.*` paralelo duplicaria o modelo e obrigaria a mudar o
   motor — exatamente o que não queremos. As tabelas ganham linhagem e chaves de negócio.
2. **Gold = `rebuild_aggregations` existente**, chamado pelos dois caminhos (gerador e
   fonte externa). Nenhum SQL específico de CSV.
3. **RAW fora do PostgreSQL**, atrás de uma abstração (`RawStorage`); implementação local
   em filesystem para DEV; metadados no banco.
4. Primeiro contrato operacional: `especialidade`, `plano`, `contrato`, `prestador`,
   `procedimento`, `beneficiario`, `receita`, `evento_assistencial` (região derivada de
   cidade/UF). `diagnostico`, `receita_contrato`, `glosa`/`coparticipacao` como entidades
   separadas ficam fora (os dois últimos são atributos do evento).
