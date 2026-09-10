# Modelo Canônico W2Health (camada Silver) — v1.2

> **Fonte de verdade:** `data_platform/contracts/*.yaml` (um arquivo por entidade).
> Este documento é a leitura em prosa. O dicionário campo-a-campo está em
> `docs/DATA_DICTIONARY.md`.

## Princípio

O motor analítico **desconhece o nome original de qualquer coluna de origem**. Cada
integração faz:

```
SOURCE MODEL  ──(data_platform/mappings/*.yaml)──▶  W2HEALTH CANONICAL MODEL (Silver)
                                                          │
                                                          ▼
                                              SQL analítico W2Health (Gold/Serving)
```

Nenhum `SELECT ... FROM MV_TABELA_X` na camada analítica — validado por
`backend/tests/test_multitenancy.py::test_source_agnostic_mapping_para_canonico_e_agregacao`.

## Entidades

| Entidade | Grão | Chave de negócio | FKs | Obs |
|---|---|---|---|---|
| **tenant** | 1 por cliente | `id` (slug) | — | único cadastro global (sem `tenant_id`) |
| **competencia** | 1 por mês (dia 1) | `competencia` | — | calendário global (sem `tenant_id`) |
| **beneficiario** | 1 por vida (estado atual) | `(tenant_id, codigo)` | plano, contrato, regiao | `codigo` pseudonimizado; nunca CPF como chave |
| **plano** | 1 por produto/plano | `(tenant_id, codigo)` | — | segmentação ANS, coparticipação |
| **contrato** | 1 por contrato/apólice | `(tenant_id, codigo)` | plano | `data_base`/`meta_sinistralidade` = layout p/ reajuste (não usado) |
| **prestador** | 1 por prestador | `(tenant_id, codigo)` | regiao, especialidade_principal | especialidade principal define o grupo de pares (z-score) |
| **especialidade** | 1 por especialidade | `(tenant_id, codigo)` | — | grupo: clinica/cirurgica/diagnostico/terapia |
| **procedimento** | 1 por procedimento | `(tenant_id, codigo)` | especialidade | `perfil_utilizacao` apoia (não prova) hipótese de coorte |
| **evento_assistencial** | 1 por item de conta/atendimento | `(tenant_id, source_system, source_record_id)` | beneficiario, contrato, prestador, procedimento, especialidade, diagnostico | entidade mais volumosa; composição bruta/glosa/copart/líquida |
| **receita** | competência × plano | `(tenant_id, competencia, id_plano)` | plano | grão MÍNIMO para sinistralidade; vem do faturamento |
| **receita_contrato** | competência × contrato | `(tenant_id, competencia, id_contrato)` | contrato | **layout preparado — não populado nem lido na v1.2** |
| **glosa** | atributo derivado de evento | — | — | `valor_glosado` no evento; motivo é RECOMENDADO |
| **coparticipacao** | atributo derivado de evento | — | — | `valor_coparticipacao`; `faturada` vs `derivada` |

## Atributos / enumerações (não são entidades)

- `tipo_atendimento`: consulta · exame · terapia · pronto_socorro · internacao · cirurgia · opme
- `grupo_despesa` (= `procedimento.grupo_procedimento`): agrupador de análise
- `regiao`: cidade/UF/macrorregião do beneficiário e do prestador
- `faixa_etaria`: banda de saúde derivada de `data_nascimento` (idealmente por competência)
- `sexo`: M · F
- `origem_dado` (coparticipação): `faturada` · `derivada`

## Semântica financeira (canônica)

```
valor_apresentado     = despesa BRUTA apresentada pelo prestador
valor_glosado         = parcela glosada (não paga ao prestador)
valor_pago            = valor_apresentado − valor_glosado
valor_coparticipacao  = parcela de valor_pago cobrada do beneficiário
despesa_liquida       = valor_apresentado − valor_glosado − valor_coparticipacao   (DERIVADA)
```

`sinistralidade = despesa_liquida / receita × 100` (convenção do MVP; a bruta é sempre
exibida ao lado). No **escopo de contrato**, não há receita → só a composição da despesa.

## Relação com o ORM

`backend/app/models/` é o espelho técnico deste modelo no serving (PostgreSQL). Campos
que o modelo sintético tem e um cliente real **não precisa fornecer**: `contrato.vidas_alvo`
(orienta a geração), `eventos_assistenciais.cenario_tag` (QA). Campos que o cliente
**precisa** fornecer e o motor ainda não usa: `beneficiario.motivo_saida`,
`contrato.data_base`/`meta_sinistralidade`, tudo de `receita_contrato`.
