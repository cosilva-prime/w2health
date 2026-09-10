# Formato dos contratos de dados (`data_platform/contracts/*.yaml`)

Cada arquivo descreve **uma entidade canônica** do W2Health (camada Silver). É a fonte de
verdade para: o dicionário de dados (`docs/DATA_DICTIONARY.md`), o contrato de dados
(`docs/DATA_CONTRACT.md`), os mappings de integração e as regras de qualidade.

```yaml
entity: <nome_canonico>              # snake_case
version: 1                           # sobe quando o layout muda de forma incompatível
grain: "<uma frase: o que é 1 linha>"
primary_key: [<colunas>]             # inclui sempre tenant_id
business_keys:                       # 1+ combinações que identificam a linha na ORIGEM
  - [tenant_id, source_system, source_record_id]
load_strategy: FULL | INCREMENTAL_DATA | INCREMENTAL_ID | CDC | UPSERT
watermark_column: <col | null>       # coluna monotônica para carga incremental
updated_at_column: <col | null>      # p/ CDC/UPSERT
deduplication_strategy: "<texto>"
fields:
  - name: <col>
    type: string|int|bigint|numeric|date|datetime|bool|json
    nullable: true|false
    required_for: [ALL] | [<capacidade>, ...]   # ver docs/CAPABILITY_READINESS.md
    classification: internal | operational | pii | phi
        # pii  = dado pessoal (nome, CPF, CNS...)   -> nunca chave técnica, pseudonimizar
        # phi  = dado de saúde sensível (CID, evento clínico)
    description: "<texto>"
    example: <valor>
    typical_source: "<onde costuma vir no cliente>"
    transformation: "<regra origem -> canônico>"
    quality_rules: [<rule_id>, ...]   # ver data_platform/quality/rules.py
metadata_fields: [tenant_id, source_system, source_entity, source_record_id,
                  ingestion_id, ingestion_timestamp, source_updated_at,
                  reference_date, raw_payload_hash]
```

**Metadados RAW mínimos** (todos os contratos herdam): `tenant_id`, `source_system`,
`source_entity`, `source_record_id`, `ingestion_id`, `ingestion_timestamp`,
`source_updated_at` (nullable), `reference_date`, `raw_payload_hash`.
