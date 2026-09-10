# SQL de transformação — Silver → Gold → Serving

Modelos de transformação **independentes de fornecedor** e **versionáveis**. Não são
executados por nenhum orquestrador na v1.2 (não há Airflow/ADF) — são o alvo para quando
um pipeline real for construído (`docs/DATA_PLATFORM_ARCHITECTURE.md`).

```
raw/<entidade>        (preserva o dado original + metadados de ingestão)
   │  aplica mapping (data_platform/mappings/*.yaml)  →  colunas CANÔNICAS
   ▼
silver/<entidade>     (modelo canônico W2Health — layout de data_platform/contracts/*.yaml)
   │  agregações (INSERT ... SELECT ... GROUP BY)
   ▼
gold/agg_*            (camada analítica — o que o motor lê)
   │
   ▼
serving/              (PostgreSQL da aplicação — hoje == gold; ver observação abaixo)
```

Convenções:
- Todo SELECT recebe `:tenant_id` e filtra por ele. Nunca `FROM <TABELA_DE_FORNECEDOR>`.
- Silver só referencia `raw.*` + catálogos canônicos. Gold só referencia `silver.*`.
- Os arquivos `gold/*` são a **especificação** das mesmas agregações que
  `backend/app/seed/aggregate.py` produz hoje para a massa sintética — quando o pipeline
  real existir, `aggregate.py` é substituído por estes SQLs rodando sobre `silver.*`.

## Serving

No estágio atual, **o PostgreSQL da aplicação é a camada de serving** e as tabelas `agg_*`
são materializadas diretamente nele pelo seed. `serving/` documenta esse contrato: a API
só lê `agg_sinistralidade_competencia`, `agg_competencia_dimensao`,
`agg_prestador_competencia`, `agg_beneficiario_competencia`, `agg_contrato_competencia`
(+ catálogos + `eventos_assistenciais` no detalhe de 1 beneficiário / escopo de contrato).
No futuro o serving pode virar outra tecnologia (DW, query engine) sem mudar a API.
