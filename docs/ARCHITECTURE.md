# Arquitetura — W2Health Intelligence

Monolito modular. Sem microserviços. Três serviços no Compose + um comando de seed.

```
┌───────────────┐   HTTP/JSON    ┌──────────────────────────────────────┐        ┌────────────┐
│  frontend     │ ─────────────▶ │  backend (FastAPI)                    │ ─────▶ │ postgres16 │
│  Next.js 14   │ ◀───────────── │  api → services → analytics          │        │            │
│  TS/Tailwind  │                │        repositories (SQL)             │        │  camada    │
│  Recharts/SWR │                │  seed/  (gerador + agregações)        │        │  fonte +   │
└───────────────┘                └──────────────────────────────────────┘        │  analítica │
     :3000                                    :8010→:8000                         └────────────┘
                                                                                   :15432→:5432
```

## Backend — camadas (nada de regra analítica no endpoint)

```
app/
  core/          config (pydantic-settings), logging, faixas etárias
  db/            engine + Session (SQLAlchemy 2.0, síncrono), Base declarativa
  models/        ORM — catálogos, carteira, eventos, camada analítica (agg_*), config (v1.1)
  schemas/       Pydantic — só os endpoints de escrita usam (regras de alerta, v1.1)
  repositories/  analytics_repo.py — consultas SQL (text()) sobre agg_* e fato bruta;
                 config_repo.py (v1.1) — CRUD de regras_alerta. Retornam dicts/listas simples
  analytics/     O MOTOR (funções puras + orquestração):
                   formulas.py       primitivas testáveis (sinistralidade, bennet, gini,
                                     decomposicao_financeira [v1.1], ...)
                   periodo.py        competência / comparações (MoM, YoY, 12m)
                   sinistralidade.py indicador, série, executivo, decomposição num/den,
                                     composicao() [v1.1]
                   decomposition.py  explicar() e drill() — fatores + bridge por fator
                   cohorts.py        [v1.1] análise de coortes + fato/hipótese/a_investigar
                   procedimentos.py  lista, detalhe, bridge
                   providers.py      ranking de contribuição, detalhe, z-score de pares, anomalia
                   seasonality.py    esperado sazonal vs anômalo
                   insights.py       motor de regras -> INSIGHTS tipados com deep_link
                   indicadores.py    [v1.1] catálogo fechado de indicadores para alertas
                   alerts.py         [v1.1] avalia regras_alerta -> ALERTAS (distinto de insight)
  api/v1/routes/ executive, sinistralidade, procedimentos, prestadores, beneficiarios,
                 insights (+ concentração, gabarito, meta, catálogos), config [v1.1], health
  seed/          config, catalogs (determinístico), affinities (idade×especialidade),
                 demographics, generator (vetorizado numpy, COPY), scenarios (9 hooks +
                 gabarito), aggregate (INSERT..SELECT no Postgres), run (CLI)
```

**Fluxo de uma request** (`GET /api/analytics/sinistralidade/explain?...`):
router → valida params (`_common.py`) → `analytics.decomposition.explicar(session, ...)` →
`repositories.analytics_repo` busca de `agg_competencia_dimensao` + `procedimentos_mes_detalhe`
→ `analytics.formulas` calcula contribuições e bridges → dict JSON com `metodologia`.

## Camada analítica (por que dimensional/agregada)

A fato bruta (`eventos_assistenciais`, ~320 mil linhas para 20 mil beneficiários) **não é
varrida em requests**, exceto no detalhe de 1 beneficiário (indexado). O seed materializa:

| Tabela | Grão | Usada por |
|---|---|---|
| `agg_sinistralidade_competencia` | competência | indicador, série, decomposição num/den |
| `agg_competencia_dimensao` | competência × dimensão × chave | `explicar` / `drill`, procedimentos |
| `agg_prestador_competencia` | competência × prestador | ranking, lista, detalhe, pares |
| `agg_beneficiario_competencia` | competência × beneficiário | concentração, lista de beneficiários |

Reconstruídas por `app/seed/aggregate.py` (roda inteiramente no PostgreSQL) ao final do
seed e via `python -m app.seed.aggregate` / `make rebuild-agg`.

## Frontend

- **App Router**. Um `FiltersProvider` (contexto) mantém `competência` e `comparação` na
  querystring; todas as telas leem daí. O drill-down da tela de Sinistralidade também vive
  na URL (`?dimensao=&chave=`), então a "jornada" é compartilhável e navegável para trás.
- **SWR** para leitura (`useApi`), `keepPreviousData` para transições suaves.
- **Recharts** para linha (evolução), barras horizontais (waterfall de contribuição) e
  mini-séries. Sem animações pesadas — prioridade clareza > estética > efeitos.
- Estados de loading / erro / vazio padronizados (`components/ui.tsx`).
- Banner permanente **"Ambiente demonstrativo — dados sintéticos"**.

## Decisões e desvios registrados

- **Sem autenticação** no MVP (decisão aprovada) — banner sempre visível.
- **SWR** em vez de TanStack Query: dependência mínima, mesmo resultado para leitura. O
  planejamento citava TanStack como sugestão, não requisito.
- **Dockerfile do backend** instala `requirements.txt` (exportado do `uv.lock`) com `pip`
  em vez de baixar o `uv` de `ghcr.io` — o ambiente de build bloqueia esse host.
- **Portas do host** 8010 / 15432 (em vez de 8000 / 5432) por colisão com serviços já
  ativos na máquina de desenvolvimento. Parametrizável em `.env`.
- **SQLAlchemy síncrono** — suficiente e mais simples para o volume local.
- Inserção do seed via **COPY FROM STDIN** (psycopg3) — ~15× mais rápido que executemany
  em conexões com latência (port-forward do Docker Desktop).
- **v1.1**: `/api/config/regras-alerta` (POST/PUT/DELETE) são os **primeiros endpoints de
  escrita** do produto — por isso ganharam schemas Pydantic tipados (`app/schemas/`),
  diferente do resto da API (que devolve `dict` livre por ser só leitura). Sem
  autenticação — dívida técnica registrada em [V1.1.md](V1.1.md).
- **v1.1**: o KPI "Sinistralidade" passou a significar a base **líquida**
  (bruta − glosas − coparticipação) por decisão explícita — ver [V1.1.md](V1.1.md)
  § Etapa B. A base bruta é sempre exibida ao lado, nunca omitida.
