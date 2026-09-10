# Template de mapeamento de origem → canônico

Como preencher um `data_platform/mappings/*.yaml` no discovery de um cliente. Um arquivo
por `(tenant, source_system, source_entity)`. Nomes de origem abaixo são **genéricos e
fictícios** — não correspondem a nenhum produto real.

## Ideia

```
CAMPO DA ORIGEM            →   CAMPO CANÔNICO W2HEALTH
source.customer_code       →   beneficiario.codigo         (após pseudonimização)
source.event_date          →   evento_assistencial.data_evento
source.billed_amount       →   evento_assistencial.valor_apresentado
source.denied_amount       →   evento_assistencial.valor_glosado
```

## Estrutura do arquivo

```yaml
source_system: "erp_faturamento"          # rótulo livre
source_entity:  "movimento_contas"        # tabela/arquivo na origem
target_entity:  "evento_assistencial"     # entidade canônica

load:
  strategy: INCREMENTAL_ID
  business_key: ["num_conta", "num_item"]
  watermark_column: "dh_atualizacao"
  updated_at_column: "dh_atualizacao"
  deduplication_strategy: "business_key + hash"

fields:
  - target_field: "data_evento"
    source_field: "dt_execucao"
    transformation: "cast date"
    required: true
    quality_rule: "evento_sem_data"
  - target_field: "competencia"
    source_field: "dt_execucao"
    transformation: "date_trunc('month', dt_execucao)"   # DECISÃO: competência de atendimento
    required: true
  - target_field: "valor_apresentado"
    source_field: "vl_bruto"
    transformation: "cast numeric"
    required: true
  - target_field: "valor_glosado"
    source_field: "vl_glosa"
    transformation: "coalesce(cast numeric, 0)"
    required: false
    default_value: "0"

constants:
  tenant_id: "operadora-alfa"
  source_system: "erp_faturamento"
```

## Regras de preenchimento

1. **Um `target_field` por linha.** Se um campo canônico vier de vários campos de origem,
   descreva a expressão em `transformation`.
2. **`required`** espelha o contrato canônico (`data_platform/contracts/<entity>.yaml`).
   Se `required: true` e a origem não tem → **bloqueia o onboarding daquela capacidade**.
3. **`quality_rule`** liga o campo a uma regra de `data_platform/quality/rules.py`.
4. **Pseudonimização** de identificadores pessoais acontece na `transformation`
   (`hash(...)` / máscara). CPF/CNS **nunca** viram `target_field` de Silver.
5. **Lookups** (`codigo` de origem → `id` canônico) são resolvidos contra a Silver de
   catálogos já carregada — carregar catálogos ANTES dos fatos.
6. Campos que a origem não tem e o canônico permite derivar (ex.: `valor_coparticipacao`,
   `despesa_liquida`, `status`) → `source_field: null` + `transformation` com a regra.

## Exemplo completo

`data_platform/mappings/exemplo_operadora_generica.yaml`.
