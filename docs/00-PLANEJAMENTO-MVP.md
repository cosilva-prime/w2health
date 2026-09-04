# W2Health Intelligence — Planejamento do MVP

> **Decision Intelligence Platform for Healthcare**
> Documento de planejamento inicial (Fases 1–3). Nenhuma linha de código escrita ainda.
> Status: **aguardando aprovação** para iniciar a implementação etapa por etapa.
> Data: 2026-09-02

---

## Tese do produto

> "Uma plataforma capaz de identificar e explicar automaticamente as principais causas
> das variações da sinistralidade de uma operadora de saúde, correlacionando informações
> financeiras e assistenciais até o nível de prestadores, procedimentos e beneficiários."

Todos os dados do MVP são **sintéticos**. O sistema roda **localmente** e é **demonstrável**
para diretoria e potenciais clientes.

---

## FASE 1 — Leitura dos requisitos

### O que este produto é (e o que não é)

- **Não é** um dashboard de sinistralidade. Calcular `Despesa / Receita` é commodity.
- **É** um **motor de atribuição de variância** que responde *"por quê"* a sinistralidade
  mudou, decompondo o delta por dimensão e, dentro de cada dimensão, separando
  **efeito frequência** de **efeito custo médio**, com drill-down determinístico até
  prestador / procedimento / beneficiário / evento.
- A inteligência é **matemática e rastreável**, não texto estático. Todo insight carrega
  os números que o geraram e a fórmula usada.
- MVP **local**, demonstrável, dados **100% sintéticos** com **padrões plantados**
  (ground truth) que o motor precisa redescobrir.

### Núcleo técnico (o que decide o sucesso)

1. **Decomposição da variação da sinistralidade** em efeito-despesa vs efeito-receita
   (numerador vs denominador). A sinistralidade pode subir só porque a receita estagnou.
2. **Decomposição da variação da despesa** por qualquer dimensão (contribuição em R$ e
   em % da variação).
3. **Bridge frequência × custo médio** por categoria, sem resíduo (método simétrico de
   Bennet), com normalização por exposição (por 1.000 beneficiários).
4. **Concentração** (top-k, Pareto, Gini) — beneficiários e prestadores.
5. **Anomalia de prestador** por comparação com pares (z-score em grupo homogêneo).
6. **Sazonalidade** — distinguir "esperado para o mês" de "anômalo" (exige ≥ 13 meses →
   YoY a partir de jan/2026).
7. **Motor de insights** — regras sobre os itens 1–6, com score de relevância e deep-link
   para a tela correspondente.

### Riscos e mitigação

| Risco | Mitigação |
|---|---|
| 100k beneficiários → volume pesado localmente | Geração parametrizável; default 20k, flag para 100k. Camada analítica pré-agregada (não consultar a fato bruta na request). |
| Decomposição com sinais quando ΔD ≈ 0 | Reportar sempre em R$ absoluto + % com denominador `Σ|contribuições|` como fallback; nunca dividir por ~0. |
| Interação frequência × custo "some" ou é dupla-contada | Método de Bennet (simétrico): soma dos efeitos = ΔD exato, sem termo residual. Laspeyres como visão alternativa. |
| Insights "parecerem" IA sem serem | Cada card tem seção "Como calculamos" com fórmula + valores. |
| Dados aleatórios demais → motor não acha nada | Cenários declarativos plantados + tabela `cenarios_gabarito` + testes que exigem detecção. |

---

## FASE 2 — Proposta

### 1) Arquitetura

**Monolito modular** (sem microserviços), 3 serviços no Compose + 1 job.

```
┌────────────┐   HTTP/JSON   ┌─────────────────────────────┐        ┌────────────┐
│  frontend  │ ────────────▶ │  backend (FastAPI)          │ ─────▶ │ postgres   │
│  Next.js   │ ◀──────────── │  api → services → analytics │        │  16        │
│  TS+Tailw. │               │  repositories (SQL)         │        │            │
└────────────┘               └─────────────────────────────┘        └────────────┘
                                     ▲
                              ┌──────┴───────┐
                              │  seeder (job)│  gera dados sintéticos + rebuild agregações
                              └──────────────┘
```

| Camada | Escolha | Racional |
|---|---|---|
| Frontend | **Next.js 14 (App Router) + TypeScript + Tailwind + shadcn/ui + Recharts + TanStack Query** | Aparência SaaS enterprise, componentes reutilizáveis, Recharts cobre linha/barra/waterfall com pouco esforço. |
| Backend | **Python 3.12 + FastAPI + Pydantic v2 + SQLAlchemy 2.0 + Alembic**, gerenciado com `uv` | Igual ao SweetERP. Swagger nativo. |
| Analítica | **SQL faz o group-by pesado; Python faz a matemática** do bridge/atribuição; `numpy`/`pandas` só no motor e no seeder | Cálculos testáveis isoladamente, sem ORM no meio. |
| Camada analítica | **Modelo dimensional (star schema) + tabelas de agregação mensais** materializadas pós-seed | Request responde em ms lendo agregados, não varrendo centenas de milhares de eventos. |
| Banco | **PostgreSQL 16** | — |
| Container | **Docker + Docker Compose** | `frontend`, `backend`, `postgres`, `seeder`. |
| Auth | Login demo único (usuário/senha fixos) OU sem login + banner. JWT stub opcional. | Não é foco do MVP. |

**Sim ao modelo dimensional** para a camada analítica — é o que torna o drill-down barato.

---

### 2) Modelo de dados

#### Camada fonte (OLTP-like) — o que o "sistema da operadora" produziria

`beneficiarios`, `planos`, `contratos`, `prestadores`, `especialidades`, `procedimentos`,
`diagnosticos`, `eventos_assistenciais`, `receitas`, `competencias`.

Complementos propostos aos campos mínimos do briefing:

- **`eventos_assistenciais`**: `id_evento, id_beneficiario, id_prestador, id_procedimento,
  id_especialidade, id_diagnostico?, data_evento, competencia (YYYY-MM),
  tipo_atendimento (consulta|exame|terapia|pronto_socorro|internacao|cirurgia|opme),
  quantidade, valor_apresentado, valor_glosado, valor_pago, regiao, cenario_tag?`
  (`cenario_tag` rastreia qual cenário injetou a linha — usado só para testes/QA, nunca
  exposto na API).
  `valor_pago = valor_apresentado − valor_glosado`. **Despesa assistencial = Σ valor_pago**.
- **`beneficiarios`**: `id_beneficiario (BEN-000001), sexo, data_nascimento, faixa_etaria,
  cidade, estado, regiao, id_plano, id_contrato, data_adesao, data_saida?, status`.
- **`prestadores`**: `id_prestador, nome_ficticio, tipo_prestador
  (hospital|clinica|laboratorio|pronto_atendimento|consultorio), cidade, estado, regiao,
  especialidade_principal, nivel_preco` (fator multiplicativo interno, não exposto).
- **`procedimentos`**: `id_procedimento, codigo, descricao, grupo_procedimento,
  id_especialidade, complexidade (1–5), custo_base, faixa_etaria_alvo`.
- **`receitas`**: `competencia, id_plano, quantidade_beneficiarios, receita_contraprestacao`.

**Faixas etárias** (bandas de saúde):
`0-1, 2-4, 5-9, 10-14, 15-19, 20-29, 30-39, 40-49, 50-59, 60-69, 70-79, 80+`.

#### Camada analítica (star schema)

- **Dimensões**: `dim_tempo` (competencia, ano, mes, mes_nome, trimestre, is_inverno),
  `dim_beneficiario`, `dim_plano`, `dim_contrato`, `dim_prestador`, `dim_especialidade`,
  `dim_procedimento`, `dim_diagnostico`, `dim_regiao`.
- **Fato**: `fato_evento` (grão = 1 evento).
- **Fato**: `fato_receita` (grão = competencia × plano).
- **Agregados materializados** (o "motor" lê daqui):
  - `agg_sinistralidade_competencia` — grão competencia:
    `receita, despesa, sinistralidade, n_benef_ativos, custo_pmpm, receita_media_benef`.
  - `agg_competencia_dimensao` — grão `competencia × tipo_dimensao × chave`:
    `rotulo, despesa, n_eventos, quantidade, n_benef, custo_medio, freq_por_mil`.
    **Tabela alta**, `tipo_dimensao ∈ {grupo_despesa, tipo_atendimento, especialidade,
    procedimento, prestador, regiao, faixa_etaria, sexo, plano}`. É o motor da decomposição.
  - `agg_prestador_competencia` — métricas para peer/anomalia.
  - `agg_beneficiario_competencia` — custo mensal por beneficiário (concentração, alto
    custo, timeline).
- `cenarios_gabarito` — ground truth dos cenários (competência-alvo, dimensão, magnitude
  esperada), consumido pelos testes.
- `seed_manifest` — seed, parâmetros, contagens, hash.

Rebuild dos agregados = passo final do seeder e comando `make rebuild-agg`.

---

### 3) Estrutura de diretórios

```
w2health/
├─ docker-compose.yml
├─ .env.example
├─ Makefile
├─ README.md
├─ docs/
│  ├─ 00-PLANEJAMENTO-MVP.md   # este documento
│  ├─ MVP.md  ARCHITECTURE.md  DATA_MODEL.md  ANALYTICS_ENGINE.md  SYNTHETIC_DATA.md
│  └─ DEMO_SCRIPT.md            # roteiro da narrativa de sucesso
├─ backend/
│  ├─ pyproject.toml  uv.lock  alembic.ini  Dockerfile
│  ├─ alembic/versions/
│  ├─ app/
│  │  ├─ main.py                # create_app()
│  │  ├─ core/                  # config, db, security, logging, deps, errors
│  │  ├─ models/                # SQLAlchemy (fonte + dimensional)
│  │  ├─ schemas/               # Pydantic (request/response + envelope)
│  │  ├─ api/v1/                # routers: executive, sinistralidade, prestadores,
│  │  │                         #          procedimentos, beneficiarios, insights, catalogos
│  │  ├─ repositories/          # SQL puro / consultas agregadas
│  │  ├─ services/              # orquestra repos + analytics para cada endpoint
│  │  └─ analytics/
│  │     ├─ sinistralidade.py        # S, ΔS p.p., evolução, 12m, YoY
│  │     ├─ decomposition.py         # numerador/denominador + contribuição por dimensão
│  │     ├─ frequency_cost.py        # bridge Bennet + Laspeyres, normalização exposição
│  │     ├─ concentration.py         # top-k, Pareto, Gini
│  │     ├─ providers.py             # peer groups, z-score, ranking contribuição
│  │     ├─ seasonality.py           # baseline YoY / média móvel, desvio
│  │     ├─ beneficiaries.py         # jornada/timeline, alto custo, frequent flyer
│  │     └─ insights.py              # regras → insights tipados + score + deep-link
│  ├─ seed/
│  │  ├─ config.py  catalogs.py  demographics.py  affinities.py
│  │  ├─ generator.py                # beneficiários, receita, eventos base
│  │  ├─ scenarios.py                # cenários declarativos + gravação do gabarito
│  │  └─ run.py                      # CLI parametrizável
│  └─ tests/
│     ├─ test_sinistralidade.py  test_decomposition.py  test_frequency_cost.py
│     ├─ test_concentration.py   test_providers_ranking.py
│     └─ test_scenarios.py            # test_cataract_frequency_scenario_detected(), etc.
└─ frontend/
   ├─ package.json  next.config.js  tailwind.config.ts  Dockerfile
   └─ src/
      ├─ app/(shell)/            # layout: sidebar, header, filtros, banner, breadcrumbs
      │  ├─ page.tsx             # Visão Executiva
      │  ├─ sinistralidade/
      │  ├─ prestadores/[id]/
      │  ├─ beneficiarios/[id]/
      │  └─ insights/
      ├─ components/             # KPICard, Waterfall, EvolutionChart, FactorsTable,
      │                         # BridgeFreqCost, ParetoChart, Timeline, InsightCard
      ├─ features/               # hooks TanStack Query por domínio
      └─ lib/                    # apiClient, formatters (R$, %, p.p.), deep-link parser
```

---

### 4) Regras do motor analítico

Notação: `t` = mês selecionado, `0` = mês de comparação (anterior, ou mesmo mês do ano
anterior). `D` = despesa assistencial (Σ valor_pago), `R` = receita assistencial
(contraprestações), `N` = nº de eventos (ou quantidade), `P = D/N` = custo médio.

#### 4.1 Sinistralidade

- `S = D / R × 100`
- `ΔS = S_t − S_0` em **pontos percentuais (p.p.)**
- Acumulado 12m: `Σ D(últimos 12) / Σ R(últimos 12) × 100`
- YoY: `S_t` vs `S_{t−12}` (disponível a partir de jan/2026)

#### 4.2 Decomposição numerador vs denominador (exata, soma = ΔS)

- Efeito despesa: `ΔD / R_0` → quanto da variação veio da despesa subindo
- Efeito receita: `D_t/R_t − D_t/R_0` → quanto veio de a receita mudar
- `Efeito_despesa + Efeito_receita = ΔS` (identidade exata)

#### 4.3 Contribuição por dimensão (para a despesa)

Para categorias `i` de uma dimensão:

- `contribuição_i = D_{i,t} − D_{i,0}`  (R$)
- `participação_i = contribuição_i / ΔD_total × 100` (com `ΔD_total` protegido;
  fallback `Σ|contribuição|`)
- Categorias novas/extintas entram naturalmente (`D_{i,0}=0` ou `D_{i,t}=0`).
- Ranking por `|contribuição_i|`; separa contribuições de alta e de baixa.

#### 4.4 Bridge frequência × custo médio (por categoria — método de Bennet, simétrico, sem resíduo)

- `ΔD = N_t·P_t − N_0·P_0`
- Efeito frequência: `(N_t − N_0) · (P_0 + P_t)/2`
- Efeito custo:      `(P_t − P_0) · (N_0 + N_t)/2`
- **Soma = ΔD exatamente.**
- Visão alternativa (Laspeyres): `freq = ΔN·P_0`, `custo = ΔP·N_0`,
  `interação = ΔN·ΔP` reportada à parte.
- Normalização por exposição: `freq_por_mil = N / benef_expostos × 1000` — reportar
  absoluto **e** normalizado, para separar "cresceu porque a carteira cresceu" de
  "cresceu de verdade".
- Classificação do **efeito principal**: se
  `|efeito_freq| ≥ 0,65·(|efeito_freq|+|efeito_custo|)` → `"frequencia"`; simétrico para
  `"custo_medio"`; senão `"misto"`.

#### 4.5 Concentração

- `top_k_share = Σ(top k) / total`
- Ponto de Pareto: menor `k` com share ≥ 80%
- Gini via curva de Lorenz sobre despesa por beneficiário / por prestador
- Frase: *"{p}% dos beneficiários concentraram {q}% da despesa do período."*

#### 4.6 Anomalia de prestador

- Peer group = `tipo_prestador` + `especialidade_principal` + faixa de porte
  (quartil de volume).
- z-score no mês para: `custo_medio_evento`, `eventos/benef_atendido`,
  `crescimento_MoM_custo`, `%_concentração_1_procedimento`.
- Flag se `z ≥ 3` em 1 métrica **ou** `z ≥ 2` em ≥ 2 métricas. Score composto ordena o
  alerta.
- Ranking de contribuição: `D_{prest,t} − D_{prest,0}` (alta e baixa).

#### 4.7 Sazonalidade

- Com ≥ 13 meses: `esperado_t = tendência_t × fator_sazonal_mês`
  (tendência = média móvel 12m; fator sazonal = média do mês vs média anual).
- `desvio = real_t − esperado_t`. Se `|desvio| > k·σ` → **anômalo**; se `real_t` alto mas
  dentro do esperado → **"variação sazonal esperada"**.
- Antes de jan/2026: fallback por média móvel; marcado como "confiança reduzida".

#### 4.8 Motor de insights

Cada insight: `{id, tipo, severidade (🔴/🟠/🟢), titulo, descricao (template + números),
metricas_suporte[], deep_link {rota, filtros}, score, metodologia}`.
`score = |impacto_R$| normalizado × |participação_na_variação| × confiança`.
Ordenado desc.

Tipos no MVP: variação de sinistralidade; fator dominante da variação; concentração em
prestadores; freq vs custo do maior movimento; internações MoM; concentração de despesa
(Pareto beneficiários); prestador fora do padrão; **melhora/redução** (verde);
sazonalidade (informativo).

---

### 5) Estratégia de geração de dados sintéticos

**Operadora fictícia: "Vida Plena". Período: jan/2025 – dez/2026 (24 meses).
`SEED` obrigatório (default 42).** `numpy.random.Generator`, todos os sorteios derivados
do seed.

**Parametrização (CLI):**
`--beneficiarios 20000|100000 --inicio 2025-01 --fim 2026-12 --seed 42 --escala-eventos 1.0`.
Default 20k; `make seed-full` gera 100k.

#### Camadas de geração (determinísticas → estocásticas)

1. **Catálogos**: 15 especialidades; ~80 procedimentos (grupo, especialidade,
   `complexidade`, `custo_base` lognormal ordenado por complexidade, faixa etária alvo,
   tipo de atendimento típico); 12 planos (ticket médio distinto); contratos; ~10 regiões
   (cidades/estados com pesos); ~120 prestadores (tipo, especialidade principal, cidade,
   `nivel_preco`).
2. **Beneficiários**: idade por pirâmide etária realista; sexo; plano/cidade por peso;
   `data_adesao`; rotatividade mensal pequena (~1%). `faixa_etaria` derivada.
3. **Receita**: por competência × plano =
   `nº benef ativos × ticket do plano × (reajuste anual em maio)`. Reajuste com defasagem
   controlada para habilitar o cenário "sinistralidade sobe pelo denominador".
4. **Eventos**: por beneficiário/mês, `Poisson(λ)` com `λ` por faixa etária × sexo.
   Cada evento: especialidade ~ matriz de afinidade **idade × especialidade**;
   procedimento | especialidade; prestador | (especialidade + cidade); `tipo_atendimento`;
   `quantidade`; `valor_apresentado ~ lognormal(custo_base × nivel_preco_prestador × ruído)`;
   `valor_glosado ~ Beta` pequeno; `valor_pago`.
5. **Coerência forçada** (validada por teste): pediatria → idade < 13; catarata → 60+;
   obstetrícia → mulheres 15–45; internação `custo_medio ≫` consulta; complexidade maior →
   custo maior; procedimento ↔ especialidade correspondente.

#### Cenários plantados

Spec declarativa: janela de competência, dimensão-alvo, prestadores/população-alvo,
fator frequência, fator custo. Cada um grava linha em `cenarios_gabarito`.

| # | Cenário | Injeção | Motor deve concluir |
|---|---|---|---|
| 1 | **Catarata** | jul/2026: freq ×1,35; custo ×1,04; 68% em 3 prestadores de oftalmo | aumento por **frequência**; concentração em 3 prestadores |
| 2 | **Internações** | set–out/2026: freq internação ×1,18; viés 60+ | alta de internações; concentração em 60+ |
| 3 | **Prestador fora do padrão** | "Hospital X": custo médio ×1,4 vs pares + freq crescente em 2026; concentra 2 procedimentos | destacar Hospital X (z-score) |
| 4 | **Alto custo** | ~30 beneficiários com terapias de altíssimo custo a partir de mar/2026 | poucos beneficiários = grande % da despesa |
| 5 | **Sazonalidade respiratória** | mai–ago (inverno) freq respiratória ×1,5, **nos dois anos** | "variação sazonal esperada", não anomalia |
| 6 | **Pronto-socorro** | ~500 beneficiários "frequent flyers" de PA, uso recorrente todo mês | grupo recorrente de PA identificado |
| 7 | **Custo médio** | 1 procedimento (ex.: OPME ortopédico): freq estável, custo médio +25% ao longo de 2026 | aumento por **custo médio**, não frequência |
| 8 | **Melhora** | fisioterapia/terapias: a partir de out/2026 freq ×0,8 (programa de gestão) | insight **verde**: redução explicada por frequência |
| 9 | **Receita estagnada** (extra) | reajuste atrasado → sinistralidade sobe em abr/2026 pelo denominador | ΔS explicada por **efeito receita**, não despesa |

**Idempotência**: seeder faz drop/recreate dos dados, grava `seed_manifest` (seed, params,
contagens, hash) e o gabarito; termina com rebuild dos agregados.

---

### 6) Telas

**Shell**: sidebar (`Visão Executiva · Sinistralidade · Prestadores · Beneficiários ·
Insights`), header com **filtros globais** (competência de referência; base de comparação:
mês anterior | mesmo mês ano anterior | 12m; plano/contrato; região; faixa etária; sexo),
**banner fixo "Ambiente demonstrativo — dados sintéticos"**, breadcrumbs que acumulam o
caminho de investigação.

1. **Visão Executiva (Home)**
   - Linha de KPIs: Sinistralidade (com **Δ p.p.** vs comparação), Receita de
     contraprestações, Despesa assistencial, Beneficiários, Custo assistencial PMPM,
     Receita média/beneficiário.
   - Gráfico: evolução mensal da sinistralidade (linha) + faixa acumulado 12m + marcador
     YoY; comparação mês anterior e mesmo mês do ano anterior.
   - **"Principais fatores de atenção"**: chips de insight coloridos (🔴🟠🟢), cada um
     **clicável → deep-link** para a análise.
   - Mini-tabela: top 5 grupos de despesa por contribuição à variação.

2. **Sinistralidade** (funcionalidade central)
   - Cabeçalho: `S_t`, `S_0`, `Δ p.p.`, mini-waterfall **efeito despesa vs efeito receita**.
   - **Waterfall de contribuição por dimensão** (default: grupo de despesa; toggle: tipo
     de atendimento, especialidade, procedimento, prestador, região, faixa etária, sexo,
     plano).
   - **Tabela de fatores**: categoria | despesa mês | despesa comp. | Δ R$ | % da variação
     | efeito principal (freq/custo/misto) | → investigar.
   - Clique em categoria → painel de drill: sub-decomposição + **bridge frequência × custo**
     (dois números lado a lado + mini-barras, com quantidade e custo médio dos dois meses)
     + bloco **"Onde investigar primeiro"** (top prestadores e beneficiários daquela
     categoria por contribuição).
   - Breadcrumb: `Sinistralidade / Oftalmologia / Catarata / Hospital X`.

3. **Prestadores**
   - **Ranking "maior contribuição para a variação de despesa"** (alta e baixa), impacto
     em R$.
   - Tabela: prestador | tipo | custo total | Δ MoM | participação % | nº eventos | benef
     atendidos | custo médio | 🚩 anomalia.
   - **Detalhe `/prestadores/{id}`**: KPIs; evolução mensal de custo/eventos/custo médio;
     principais procedimentos e especialidades; concentração (Pareto + Gini);
     **comparação com pares** (z-scores por métrica); bridge freq × custo do prestador;
     top beneficiários.

4. **Beneficiários**
   - Busca por ID (`BEN-000001`) + filtros; lista com ranking por custo no período +
     flags "alto custo" / "frequent flyer PA".
   - **Detalhe `/beneficiarios/{id}`**: perfil anonimizado (idade, sexo, plano, região);
     evolução mensal de custo; tabela de eventos (data, prestador, procedimento,
     diagnóstico, valores); **timeline**
     `Consulta → Exame → Diagnóstico → Procedimento → Internação → Retorno`.

5. **Insights**
   - Feed de insights tipados; filtros por severidade / tipo / competência; cada card com
     números de suporte, botão **"Investigar" → deep-link**, e seção expansível
     **"Como calculamos"** (fórmula + valores).

---

### 7) Endpoints

Envelope padrão: `{ data, meta: { competencia, comparacao, filtros_aplicados, gerado_em,
total? } }`. Paginação `page` / `page_size`. Toda resposta de explicação inclui
`metodologia`.

```
GET  /api/health
POST /api/auth/login                                  # demo, opcional

GET  /api/executive/overview?competencia=&comparacao=&<filtros>

GET  /api/analytics/sinistralidade?competencia=&<filtros>
GET  /api/analytics/sinistralidade/evolucao?inicio=&fim=&<filtros>
GET  /api/analytics/sinistralidade/explain?competencia=&comparacao=&dimensao=&<filtros>
GET  /api/analytics/sinistralidade/explain/{dimensao}/{chave}?competencia=&comparacao=   # drill: sub-fatores + bridge

GET  /api/analytics/procedimentos?competencia=&sort=&page=&page_size=&<filtros>
GET  /api/analytics/procedimentos/{id}?competencia=&comparacao=
GET  /api/analytics/procedimentos/{id}/bridge?competencia=&comparacao=

GET  /api/analytics/prestadores?competencia=&sort=impacto|custo|anomalia&page=&page_size=
GET  /api/analytics/prestadores/ranking-variacao?competencia=&direcao=alta|baixa&limit=
GET  /api/analytics/prestadores/{id}?competencia=&comparacao=
GET  /api/analytics/prestadores/{id}/pares?competencia=

GET  /api/analytics/beneficiarios?competencia=&sort=custo&page=&page_size=&<filtros>
GET  /api/analytics/beneficiarios/{id}
GET  /api/analytics/beneficiarios/{id}/timeline

GET  /api/analytics/concentracao?competencia=&base=beneficiario|prestador
GET  /api/analytics/insights?competencia=&severidade=&tipo=&limit=

GET  /api/catalogos/{planos|regioes|especialidades|faixas-etarias|grupos-despesa}
GET  /api/meta/competencias
```

Exemplo de `/sinistralidade/explain` (formato do briefing, estendido):

```json
{
  "data": {
    "sinistralidade_atual": 82.4, "sinistralidade_anterior": 74.6, "variacao_pp": 7.8,
    "efeito_despesa_pp": 8.9, "efeito_receita_pp": -1.1,
    "principais_fatores": [
      { "categoria": "Oftalmologia", "chave": "esp_07",
        "impacto_financeiro": 1200000, "participacao_variacao": 27.4,
        "efeito_principal": "frequencia",
        "bridge": { "efeito_frequencia": 1080000, "efeito_custo_medio": 120000,
                    "qtd_atual": 165, "qtd_anterior": 120,
                    "custo_medio_atual": 4250, "custo_medio_anterior": 4100 },
        "drill_link": "/sinistralidade/explain/especialidade/esp_07" }
    ]
  },
  "meta": { "competencia": "2026-07", "comparacao": "mes_anterior" },
  "metodologia": "DS = D_t/R_t - D_0/R_0 (p.p.). Contribuicao_i = D_i,t - D_i,0. Bridge: Bennet simetrico."
}
```

---

### 8) Backlog do MVP (épicos → histórias)

| Épico | Histórias |
|---|---|
| **A. Fundações** | A1 repo + docker-compose (postgres/backend/frontend/seeder) + Makefile · A2 FastAPI skeleton + config + health + CORS · A3 SQLAlchemy + Alembic baseline · A4 Next.js skeleton + Tailwind + shell (sidebar/header/banner/breadcrumbs) + apiClient |
| **B. Modelo & camada analítica** | B1 migrations camada fonte · B2 migrations dimensional + agregados · B3 job de rebuild dos agregados |
| **C. Gerador sintético** | C1 catálogos · C2 beneficiários + receita · C3 motor de eventos com afinidades demográficas · C4 cenários 1–9 declarativos + `cenarios_gabarito` · C5 CLI parametrizável + `seed_manifest` + comando docker |
| **D. Motor analítico** | D1 sinistralidade + evolução + 12m + YoY · D2 decomposição numerador/denominador · D3 contribuição por dimensão · D4 bridge freq × custo (Bennet + Laspeyres + exposição) · D5 concentração (top-k/Pareto/Gini) · D6 anomalia de prestador + ranking contribuição · D7 sazonalidade · D8 motor de insights (templates + score + deep-link) |
| **E. API** | E1 executive/overview · E2 sinistralidade + evolucao + explain + explain/drill · E3 procedimentos · E4 prestadores + ranking + pares · E5 beneficiarios + timeline · E6 concentracao + insights + catálogos + meta |
| **F. Frontend** | F1 Visão Executiva · F2 Sinistralidade (waterfall + tabela + drill + bridge) · F3 Prestadores (ranking + detalhe + pares) · F4 Beneficiários (detalhe + timeline) · F5 Insights (feed + deep-link + "como calculamos") · F6 filtros globais + breadcrumbs + loading/empty/error |
| **G. Testes & docs** | G1 testes de cálculo (sinistralidade, %, p.p., custo médio, frequência, contribuição, ranking, concentração, efeito freq, efeito custo) · G2 testes de detecção de cenário (`test_cataract_frequency_scenario_detected`, …) vs gabarito · G3 README + `docs/*.md` · G4 seed de demo curada + `DEMO_SCRIPT.md` |

---

## FASE 3 — Plano de implementação por etapas

Cada etapa termina com: entregável **demonstrável**, testes verdes, migrations
versionadas, `docs/` atualizado.

| Etapa | Conteúdo | Entregável demonstrável |
|---|---|---|
| **0** | Este documento | ✅ Aprovado em 2026-09-02 |
| **1** | A1–A4 | ✅ **Concluída** — stack sobe no Docker; shell do frontend consome `/api/health`. Detalhes: [ETAPA-01.md](ETAPA-01.md) |
| **2** | B1–B2 | ✅ 17 tabelas, migration aplica limpo |
| **3** | C1–C3 + B3 | ✅ seed 20k (~320 mil eventos, ~50s), coerência demográfica testada |
| **4** | C4–C5 | ✅ 9 cenários plantados + `cenarios_gabarito`; `--beneficiarios 100000` OK |
| **5** | D1–D4 + G1 | ✅ motor + 23 testes de fórmula verdes |
| **6** | E1–E2 + F1–F2 | ✅ Home → explain → waterfall → drill catarata → bridge "frequência" |
| **7** | D5–D6 + E3–E4 + F3 | ✅ ranking, detalhe, z-score de pares, flag de anomalia |
| **8** | E5 + F4 | ✅ navegação até o beneficiário + timeline; concentração |
| **9** | D7–D8 + E6 + F5 | ✅ feed de insights com deep-link e "como calculamos" |
| **10** | G2 + F6 + G3–G4 | ✅ 10 testes de cenário verdes; docs completos; `docs/DEMO.md` |

**Critério de pronto do MVP** = executar `DEMO_SCRIPT.md` inteiro: diretor abre → vê alta →
sistema explica fatores → seleciona um → chega a procedimentos → identifica prestadores →
chega a beneficiários/eventos → distingue frequência de custo médio → recebe insights
derivados matematicamente dos dados.

---

## FASE 4 — Decisões (aprovadas em 2026-09-02)

Registradas em detalhe (e marcadas como decisões **do MVP**, não arquiteturais
definitivas) em [DECISOES-MVP.md](DECISOES-MVP.md).

1. **Local do projeto**: repositório novo e independente em `projetos/w2health/`.
2. **Volume default**: **20.000** beneficiários, parametrizável para 100.000.
3. **Gráficos**: **Recharts**.
4. **Auth**: MVP **sem autenticação**; banner "Ambiente demonstrativo — dados sintéticos"
   mantido.
5. **Base de comparação padrão**: **mês anterior (MoM)**; demais opções permanecem no
   escopo.
6. **Método do bridge**: **Bennet simétrico** como padrão; Laspeyres como alternativa.
7. **Frontend**: **Next.js (App Router)** + TypeScript + Tailwind.

---

*Ambiente demonstrativo — dados sintéticos. Nenhum dado de pessoa real é utilizado.*
