# Data Quality — W2Health (v1.2)

Regras mínimas de qualidade aplicadas às **linhas canônicas** (Silver), antes de promover
para Gold/Serving. Implementação executável e testada:
[`data_platform/quality/rules.py`](../data_platform/quality/rules.py)
(testes: `backend/tests/test_data_quality.py`). Catálogo em tabela:
[`data_platform/quality/rules.md`](../data_platform/quality/rules.md).

## Severidades

| Severidade | Significado | Efeito no pipeline |
|---|---|---|
| **ERROR** | dado inconsistente que invalida a análise | **bloqueia** a entidade — a carga não avança para Silver/Gold; corrigir origem/mapping e reprocessar |
| **WARNING** | anomalia que não invalida, mas precisa de atenção | **continua**; grava em `data_quality_results`; pode exigir revisão manual |
| **INFO** | observação | apenas anotação |

Decisão programática: `rules.bloqueia_processamento(violacoes)` → `True` se houver
qualquer `ERROR`.

## Regras

| id | Entidade | Severidade | Condição |
|---|---|---|---|
| `tenant_id_ausente` | todas | ERROR | linha sem `tenant_id` |
| `benef_inexistente_em_evento` | evento | ERROR | `id_beneficiario` não existe na Silver |
| `contrato_inexistente` | evento, beneficiario | ERROR | `id_contrato` referenciado não existe |
| `prestador_inexistente` | evento | ERROR | `id_prestador` não existe |
| `valor_negativo` | evento, receita | ERROR | `valor_apresentado`/`valor_pago`/`receita_contraprestacao` < 0 |
| `competencia_invalida` | evento, receita | ERROR | competência não é o 1º dia de um mês válido |
| `evento_sem_data` | evento | ERROR | `data_evento` ausente |
| `glosa_maior_que_apresentado` | evento | ERROR | `valor_glosado` > `valor_apresentado` |
| `data_saida_antes_adesao` | beneficiario | ERROR | `data_saida` < `data_adesao` |
| `evento_duplicado` | evento | WARNING | `(source_system, source_record_id)` repetido no lote |
| `receita_duplicada` | receita | WARNING | `(competencia, id_plano)` repetido |
| `despesa_liquida_inconsistente` | evento | WARNING | `\|despesa_liquida − (bruta − glosa − copart)\| > 0,01` (será recalculada na Gold) |
| `coparticipacao_acima_permitido` | evento | WARNING | `valor_coparticipacao` > `valor_pago` |

## Onde os resultados ficam

`data_quality_results` (tenant-aware): `run_id`, `rule_id`, `entity`, `severity`,
`records_checked`, `records_failed`, `sample` (JSON com exemplos). Preenchida pelo
pipeline futuro; vazia na v1.2.

## Bloqueio vs. continuação — resumo

- **Bloqueia** (`ERROR`): referências quebradas (beneficiário/contrato/prestador
  inexistentes), valores impossíveis (negativos, glosa > apresentado), datas inválidas
  (competência, evento sem data, saída antes da adesão), `tenant_id` ausente.
- **Continua com alerta** (`WARNING`): duplicidades (dedup resolve), inconsistência de
  despesa líquida (Gold recalcula), coparticipação acima do pago (registra e segue).

## Extensões previstas (não na v1.2)

Volumetria por competência (queda/pico anômalo de linhas), completude por campo (%
preenchido), consistência temporal (competência de pagamento << competência de
atendimento), reconciliação com o fechamento contábil do cliente.
