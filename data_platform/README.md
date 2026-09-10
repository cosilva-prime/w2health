# W2Health — Data Platform

Fundação de dados do W2Health como **SaaS multi-tenant** (introduzida na v1.2). É
**estrutura, contratos e SQL de referência** — **nenhum pipeline roda aqui ainda** e
nenhum conector real (MV/Tasy/Benner/TISS) existe.

O que este diretório responde:

| Pergunta | Onde |
|---|---|
| Qual formato de dados o W2Health espera? | `contracts/*.yaml` + `docs/CANONICAL_DATA_MODEL.md` + `docs/DATA_DICTIONARY.md` |
| O que é obrigatório vs. desejável? | `docs/DATA_CONTRACT.md` |
| Como um cliente novo entra? | `docs/CLIENT_ONBOARDING.md` |
| Como dados de sistemas diferentes viram o modelo W2Health? | `mappings/` + `docs/INTEGRATION_GUIDE.md` + `docs/SOURCE_MAPPING_TEMPLATE.md` |
| Como isolamos cada cliente? | `docs/MULTI_TENANCY.md` |
| O cliente tem dados para qual capacidade? | `docs/CAPABILITY_READINESS.md` |
| Quais queries alimentar quando conectarmos um sistema real? | `sql/` (silver → gold → serving) |
| Como o motor deixa de depender da massa sintética? | `docs/DATA_PLATFORM_ARCHITECTURE.md` |

## Estrutura

```
data_platform/
  contracts/      13 contratos de dados canônicos (YAML) + _schema.md
  mappings/       _template.yaml + exemplo_operadora_generica.yaml (nomes fictícios)
  sql/
    silver/       raw -> modelo canônico W2Health
    gold/         silver -> agg_* (camada analítica)
    serving/      gold -> o que a API lê (hoje: o próprio PostgreSQL)
  quality/        rules.py (executável, testado) + rules.md
  examples/       amostra do layout canônico
```

## Camadas (Data Platform × Application Platform)

```
FONTES DO CLIENTE → INGESTÃO → RAW/BRONZE → SILVER (canônico) → GOLD (agg_*) → SERVING → W2Health API → Frontend
└──────────────────────── DATA PLATFORM ───────────────────────┘   └── APPLICATION PLATFORM ──┘
```

O PostgreSQL atual é **banco da aplicação + serving analítico + configuração** — **não** o
repositório bruto definitivo. Ver `docs/DATA_PLATFORM_ARCHITECTURE.md` (cloud-agnostic).
