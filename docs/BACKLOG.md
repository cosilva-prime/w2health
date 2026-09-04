# Backlog do MVP — status

Legenda: ✅ concluído · 🔷 parcial (documentado)

## EPIC A — Fundações  ✅
- A1 repo + docker-compose (postgres/backend/frontend) + Makefile ✅
- A2 FastAPI skeleton + config + `/health` + CORS ✅
- A3 SQLAlchemy 2.0 + Alembic + modelos ✅
- A4 Next.js + Tailwind + shell (sidebar/header/banner/breadcrumbs) + apiClient ✅

## EPIC B — Modelo & camada analítica  ✅
- B1 migrations camada fonte ✅
- B2 migrations camada analítica (agg_*, gabarito, manifest) ✅
- B3 job de rebuild das agregações (`app/seed/aggregate.py`, `make rebuild-agg`) ✅

## EPIC C — Gerador sintético  ✅
- C1 catálogos determinísticos ✅
- C2 beneficiários + receita (calibrada) ✅
- C3 motor de eventos com afinidades demográficas (NumPy + Gumbel-max + COPY) ✅
- C4 cenários 1–9 declarativos + `cenarios_gabarito` ✅
- C5 CLI parametrizável + `seed_manifest` + comando no container ✅

## EPIC D — Motor analítico  ✅
- D1 sinistralidade + evolução + 12m + YoY ✅
- D2 decomposição numerador/denominador ✅
- D3 contribuição por dimensão (9 dimensões) ✅
- D4 bridge frequência × custo (Bennet padrão + Laspeyres + bridge composto por procedimento) ✅
- D5 concentração (top-k / Pareto / Gini) ✅
- D6 anomalia de prestador (z-score vs pares) + ranking de contribuição ✅
- D7 sazonalidade (esperado sazonal vs anômalo) ✅
- D8 motor de insights (10 regras, score, deep-link, metodologia) ✅

## EPIC E — API  ✅
- E1 `/executive/overview` ✅
- E2 `/analytics/sinistralidade` + `/evolucao` + `/explain` + `/explain/{dim}/{chave}` ✅
- E3 `/analytics/procedimentos` + `/{id}` + `/{id}/bridge` ✅
- E4 `/analytics/prestadores` + `/ranking-variacao` + `/anomalias` + `/{id}` ✅
- E5 `/analytics/beneficiarios` + `/{id_ou_codigo}` + `/{...}/timeline` ✅
- E6 `/analytics/concentracao` + `/analytics/insights` + `/analytics/gabarito` + `/meta/competencias` + `/catalogos/{nome}` ✅

## EPIC F — Frontend  ✅
- F1 Visão Executiva (KPIs, evolução, fatores de atenção, top grupos) ✅
- F2 Sinistralidade (num/den, seletor de dimensão, waterfall, tabela de fatores, drill com bridge + "onde investigar", breadcrumb na URL) ✅
- F3 Prestadores (ranking, anomalias, lista) + `/prestadores/[id]` (KPIs, bridge, pares/z-score, série, procedimentos, concentração) ✅
- F4 Beneficiários (lista + filtros + busca) + `/beneficiarios/[id]` (perfil, evolução, eventos, timeline) ✅
- F5 Insights (feed, filtro por severidade, "Como calculamos", "Investigar" → deep-link) ✅
- F6 filtros globais (contexto + URL), breadcrumbs, estados loading/vazio/erro, responsividade ✅

## EPIC G — Testes & docs  ✅
- G1 testes de fórmula (23) — sinistralidade, %, p.p., custo médio, frequência, contribuição, Bennet, Laspeyres, concentração, Gini, severidade ✅
- G2 testes de cenário (10) + testes de endpoint (10) ✅
- G3 README + docs/MVP, ARCHITECTURE, DATA_MODEL, ANALYTICS_ENGINE, SYNTHETIC_DATA, BACKLOG ✅
- G4 roteiro de demonstração `docs/DEMO.md` ✅

## v1.1 — Evolução pós-feedback especialista  ✅

Ver [V1.1.md](V1.1.md) para o detalhamento completo. Resumo:

- **Etapa A** — coortes de beneficiários + FATO/HIPÓTESE/A_INVESTIGAR (`cohorts.py`),
  `procedimentos.perfil_utilizacao`, dimensão `contrato`, endpoint `/explain/.../causas`,
  seção "Por que caiu?" no drill existente. ✅
- **Etapa B** — composição financeira bruta/glosa/coparticipação/líquida
  (`valor_coparticipacao`, `planos.tem_coparticipacao`), decomposição de 4 efeitos
  (identidade exata), endpoint `/composicao`, seção "Composição da despesa" (Home +
  Sinistralidade), 4 novos cenários sintéticos (S10–S13). ✅
- **Etapa C** — separação Insight × Alerta, catálogo fechado de indicadores
  (`indicadores.py`), regras de alerta com CRUD (`regras_alerta`), tela
  `/configuracao/insights`, aba "Alertas configurados" em `/insights`. ✅
- Testes: 52 → **81** (todos verdes; suíte anterior 100% preservada).
- **Não implementado, por decisão explícita**: reajuste contratual — permanece só como
  análise em [EVOLUCAO_FEEDBACK_ESPECIALISTA.md](EVOLUCAO_FEEDBACK_ESPECIALISTA.md).

## Roadmap (fora do escopo)

**Reajuste contratual** (motor de simulação parametrizável — analisado, não
implementado) · Autenticação / multi-tenant (pré-requisito real antes de expor
`/api/config/*` publicamente) · integrações reais (MV, Tasy, Benner, TISS) · dados reais ·
LLM / chatbot para narrativa · ML (previsão de sinistralidade, detecção de fraude) ·
decomposição de glosa/coparticipação propagada a todas as dimensões ("Fase B") ·
Patient Journey completo · faixa etária recalculada por competência · billing · deploy
cloud · app mobile · linguagem de expressões livre para regras de alerta.
