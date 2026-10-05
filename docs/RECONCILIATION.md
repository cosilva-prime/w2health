# Reconciliação de carga — W2Health (Fase 2)

Antes de publicar uma carga, o W2Health confere se o que entrou é o que chegou e se a
camada analítica bate com a Silver. Código: `backend/app/data_platform/reconciliation.py`.
Roda **dentro** da transação de publicação, depois de Silver e Gold.

## 1. Resultado por verificação

| Status | Regra | Efeito |
|---|---|---|
| **PASS** | diferença = 0 | — |
| **WARNING** | 0 < \|diferença\| ≤ tolerância declarada no mapping | publica; o WARNING fica registrado e visível na ingestão |
| **FAIL** | \|diferença\| > tolerância | **rollback** — nada publicado; ingestão `FAILED` com o motivo |

Tolerâncias vêm do mapping (`reconciliation.financial_tolerance_abs` em R$,
`count_tolerance_abs` em registros). **Padrão = 0**: não há tolerância silenciosa.
Valores são comparados com 2 casas decimais.

## 2. Verificações

| `check_id` | Entidade | Escopo | Esperado | Obtido |
|---|---|---|---|---|
| `contagem_recebidas` | evento, receita, beneficiário | total | linhas recebidas | válidas + rejeitadas + duplicadas descartadas |
| `eventos_registros_silver` | evento | competência | eventos válidos do arquivo | eventos na Silver desta ingestão |
| `eventos_valor_apresentado_silver` | evento | competência | Σ valor_apresentado do arquivo | Σ na Silver desta ingestão |
| `gold_eventos` | agg_sinistralidade_competencia | competência | eventos na Silver do tenant | `eventos` na Gold |
| `gold_despesa_bruta` | idem | competência | Σ apresentado na Silver | `despesa_bruta` |
| `gold_despesa_liquida` | idem | competência | Σ (apresentado − glosado − coparticipação) | `despesa_liquida` |
| `receita_silver` | receita | competência | Σ receita do arquivo | Σ na Silver |
| `gold_receita` | agg_sinistralidade_competencia | competência | Σ receita na Silver | `receita` na Gold |
| `beneficiarios_silver` | beneficiário | total | beneficiários válidos | linhas da Silver tocadas pela ingestão |

Exemplo real (tenant `vida-plena-csv`, pacote de 18 competências): **130 verificações, todas
PASS** — 3 de contagem, 18 × 5 de eventos, 18 × 2 de receita e 1 de beneficiários.

## 3. Onde ver

`reconciliation_results` (com RLS) por ingestão; Admin → Integrações → coluna
"Reconciliação" e "Detalhes"; `GET /api/admin/tenants/{t}/ingestion-runs/{id}`.

## 4. Testes

`test_reconciliacao_pass_warning_fail_com_tolerancia_explicita` (unidade) e
`test_carga_publicada_e_reconciliada` (ponta a ponta).

## 5. O que a reconciliação NÃO cobre

Conferência contra totais **externos** informados pelo cliente (ex.: relatório financeiro
oficial do mês). Recomendação para a homologação: o cliente envia os totais por competência
(eventos, valor apresentado, receita) e a equipe compara com a Gold antes do estado
`HOMOLOGATED` — passo 17 de [CLIENT_ONBOARDING.md](CLIENT_ONBOARDING.md).
