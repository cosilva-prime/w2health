# Mapping framework — SOURCE → canônico (Fase 2)

Cada fonte de um cliente tem um mapping **declarativo** (YAML), **versionado** e
**validado antes de qualquer carga**. Não há código no YAML: as transformações são um
conjunto fechado e testado. Código: `backend/app/data_platform/mapping.py`.
Exemplo executável: [`data_platform/mappings/generic_operator_v1.yaml`](../data_platform/mappings/generic_operator_v1.yaml).

## 1. Arquivo e versão

- local: `data_platform/mappings/<mapping_id>_v<version>.yaml`;
- a fonte (`source_connections.configuration`) aponta `mapping_id` + `mapping_version`;
- mudança incompatível = **novo arquivo** `_v2` e troca explícita na fonte; a versão usada
  fica gravada em cada ingestão (`ingestion_runs.mapping_ref = generic_operator@v1`).

## 2. Estrutura

```yaml
mapping_id: generic_operator          # [a-z][a-z0-9_]
version: 1
description: "…"
source_format:
  type: csv
  delimiter: ";"
  encoding: utf-8
  decimal_separator: ","              # "1.234,56" → 1234.56
  date_formats: ["%d/%m/%Y"]          # tentados em ordem (+ ISO como fallback)
quality:
  max_rejected_ratio: 0.0             # fração de linhas rejeitadas tolerada por entidade
reconciliation:
  financial_tolerance_abs: 0.00       # R$ aceito como WARNING
  count_tolerance_abs: 0
entities:
  - source_entity: eventos            # arquivo eventos.csv
    target_entity: evento_assistencial
    required: true                    # arquivo obrigatório no pacote
    load_strategy: COMPETENCIA_SNAPSHOT   # ou UPSERT (padrão; dimensões)
    fields:
      source_record_id: {source: id_item}
      beneficiario_codigo: {source: matricula, normalize: [strip, upper]}
      data_evento: {source: dt_atendimento, type: date}
      tipo_atendimento:
        source: tipo_guia
        map: {"1": consulta, "2": exame, "3": terapia}
      valor_glosado: {source: vl_glosa, type: decimal, default: 0}
```

Chaves desconhecidas em qualquer nível são **erro** (evita typo silencioso).

## 3. Transformações permitidas

| Chave do campo | Efeito |
|---|---|
| `source` | coluna de origem (rename). Atalho: `campo: coluna` |
| `type` | `string` · `int` · `decimal` · `date` · `month` · `bool` (precisa ser compatível com o tipo canônico; `month` aceita data e trunca para o dia 1) |
| `required` | não pode **afrouxar** um obrigatório do contrato canônico |
| `default` | valor quando ausente/vazio (obrigatório quando não há `source`) |
| `normalize` | `strip`, `upper`, `lower`, `collapse_spaces`, `digits_only` (em ordem) |
| `map` / `map_default` | de-para de valores; os destinos precisam pertencer ao vocabulário canônico |
| `date_format` | formato específico do campo |

`bool` aceita `1/0, true/false, s/n, sim/não, y/n, yes/no`.

## 4. Validação do mapping (antes da carga)

`parse_mapping` recusa: `target_entity` inexistente; campo canônico inexistente; tipo
incompatível; obrigatório canônico sem mapeamento (nem `default`); obrigatório marcado como
opcional; normalização desconhecida; valor de `map` fora do vocabulário;
`COMPETENCIA_SNAPSHOT` em dimensão. Mapping inválido → a fonte nem é cadastrada e o
pipeline não começa (`test_mapping_invalido_e_recusado`).

## 5. Aplicação por linha

Cada linha vira uma linha canônica **ou** uma rejeição com motivo (`campo: tipo inválido`,
`campo: obrigatório ausente`, `campo: valor fora do vocabulário`) e número da linha.
Coluna de origem ausente no arquivo rejeita a entidade inteira (`colunas_ausentes`).
Rejeições alimentam o Data Quality ([DATA_QUALITY.md](DATA_QUALITY.md)).

## 6. Contrato operacional v1

O contrato canônico (`data_platform/contracts/*.yaml`) é a fonte de verdade. O subconjunto
executável está em `backend/app/data_platform/canonical.py`. Diferenças **deliberadas**,
porque o serving atual precisa do dado:

| Campo | Contrato canônico (`contracts/*.yaml`) | Contrato operacional v1 (carga) | Motivo |
|---|---|---|---|
| `prestador.id_regiao` (via `cidade`/`uf`) | nullable | `cidade` e `uf` obrigatórios | região do prestador nas telas e no detector de anomalias; a região é derivada da UF |
| `prestador.id_especialidade_principal` | nullable (`required_for: provider`) | obrigatório | grupo de pares da detecção de anomalia |
| `beneficiario.id_contrato` | nullable (`required_for: contract, beneficiary`) | obrigatório | Contract Intelligence agrupa por contrato |
| `beneficiario` região (`cidade`/`uf`) | — | obrigatório | serving atual exige região do beneficiário |
| `evento.competencia` | not null | opcional na carga | se ausente: mês de `data_evento` — **decisão de onboarding a registrar** |
| `evento.valor_pago` | not null | opcional na carga | se ausente: `valor_apresentado − valor_glosado` |
| `evento.valor_glosado` / `valor_coparticipacao` | not null | opcional na carga | se ausente: 0 — cobertura registrada como INFO no DQ |

Os campos opcionais "na carga" continuam **preenchidos** na Silver (not null) pelas
derivações acima, declaradas no próprio contrato.

Chaves estrangeiras chegam por **código de negócio** (`plano_codigo`, `beneficiario_codigo`…)
e são resolvidas para ids técnicos na Silver. A região é derivada de UF pela divisão
regional oficial do IBGE; `grupo` de especialidade ausente vira "não informado". Nenhuma
outra regra de negócio é inventada.

## 7. Como criar o mapping de um cliente

1. Preencher [SOURCE_DISCOVERY_TEMPLATE.md](SOURCE_DISCOVERY_TEMPLATE.md) com o cliente.
2. Copiar `data_platform/mappings/_template.yaml` para `<cliente>_<origem>_v1.yaml`.
3. Mapear campo a campo ([SOURCE_MAPPING_TEMPLATE.md](SOURCE_MAPPING_TEMPLATE.md)); toda
   suposição (ex.: competência derivada) vai como comentário e no registro de onboarding.
4. Rodar `pytest tests/test_data_platform_unit.py` + uma carga numa fonte de homologação.
