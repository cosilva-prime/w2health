# Onboarding de dados de um cliente — W2Health

Fluxo para conectar uma operadora real. **Nenhuma etapa está automatizada na v1.2** — é o
roteiro que a automação futura vai seguir.

## Fluxo

```
Cliente → Fontes → Mapping → RAW → Data Quality → Silver → Gold → Serving → Validação → Produção
```

## Checklist (12 passos)

| # | Passo | Entregável | Ferramenta / referência |
|---|---|---|---|
| 1 | **Cadastrar o tenant** | linha em `tenants` (slug, nome, status=`onboarding`) | `INSERT INTO tenants ...` |
| 2 | **Identificar as fontes** | lista de sistemas (assistencial, faturamento, cadastro, atuária) + tipo de acesso (DB/API/arquivo) | entrevista técnica; `source_connections` |
| 3 | **Inventariar entidades** | quais entidades canônicas cada fonte alimenta e com que frequência/volume | `source_entities` (target_entity, load_strategy) |
| 4 | **Preencher o mapping** | 1 `data_platform/mappings/<tenant>__<source>__<entity>.yaml` por entidade | `mappings/_template.yaml`; `docs/SOURCE_MAPPING_TEMPLATE.md` |
| 5 | **Validar conectividade** | amostra extraída de cada fonte (sem dado sensível em claro) | conector em modo dry-run |
| 6 | **Executar carga RAW** | `raw/<tenant>/<entidade>/...` + linha em `ingestion_runs` | conector |
| 7 | **Rodar Data Quality** | relatório de violações (`data_quality_results`) | `data_platform/quality/rules.py`; `docs/DATA_QUALITY.md` |
| — | ↳ se houver `ERROR` | corrigir origem ou mapping e voltar ao passo 6 | — |
| 8 | **Transformar para Silver** | `silver.*` populada, layout = `data_platform/contracts/*.yaml` | `data_platform/sql/silver/*` |
| 9 | **Executar Gold** | `gold.agg_*` reconstruídas para o tenant | `data_platform/sql/gold/*` (equivalente a `app.seed.aggregate`) |
| 10 | **Popular Serving** | `agg_*` no PostgreSQL da aplicação (ou view sobre Gold) | `data_platform/sql/serving/*` |
| 11 | **Validar indicadores** | conferir sinistralidade, PMPM, top drivers e 2–3 casos conhecidos com a área técnica do cliente | comparação com relatório atual da operadora |
| 12 | **Liberar módulos** | marcar capacidades ✅/🟡/❌ e ativar o tenant (`status=ativo`) | `docs/CAPABILITY_READINESS.md` |

## Decisões de onboarding a registrar (por tenant)

- **Competência**: de *atendimento* ou de *pagamento*? (muda o resultado)
- **Coparticipação**: vem por evento (faturada) ou derivada da regra do plano (estimada)?
- **Glosa tardia / reversão**: janela de reprocessamento de lotes.
- **Vínculo beneficiário↔contrato**: estado atual ou histórico por data?
- **Pseudonimização**: algoritmo de hash de `codigo`; CPF/CNS ficam só em RAW cifrado.
- **Retenção**: janela de histórico e política de expurgo.

## Pré-requisitos de plataforma (Fase 2, antes do 1º cliente real)

Autenticação + resolução de tenant por request + Row-Level Security no PostgreSQL
(ver `docs/MULTI_TENANCY.md`). Sem isso, o produto opera single-tenant.
