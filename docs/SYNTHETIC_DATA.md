# Dados sintéticos — W2Health Intelligence

Gerador: `backend/app/seed/`. CLI: `python -m app.seed.run`.
**100% fictício.** Operadora **Vida Plena**. Sem nomes, CPF, CNS ou endereços reais.

## Parâmetros (`SeedConfig`)

| Flag | Default | Descrição |
|---|---|---|
| `--seed` | 42 | semente — reprodutibilidade total |
| `--beneficiarios` | 20000 | tamanho da carteira (testado até 100000) |
| `--inicio` / `--fim` | 2025-01 / 2026-12 | janela (24 competências) |
| `--escala` | 1.0 | multiplicador da taxa de eventos |
| `--no-cenarios` | — | gera a base sem os cenários intencionais |

Volume default: ~20 mil beneficiários, ~120 prestadores, 85 procedimentos, 15
especialidades, 12 planos, 12 contratos, ~40 diagnósticos, **~320 mil eventos**, 24 meses.
Tempo: ~35–65 s (COPY + agregação no Postgres). Grava `seed_manifest` e `cenarios_gabarito`.

## Pipeline (`run.py`)

1. `wipe_dados` — limpa tudo (respeita FKs), preserva `alembic_version`.
2. `load_catalogos` — insere competências, regiões, planos, contratos, especialidades,
   procedimentos, diagnósticos e prestadores (`catalogs.py`, determinístico).
3. `generate_beneficiarios` — pirâmide etária realista, sexo, plano/região por peso,
   `data_adesao` (82% já ativos antes do início), rotatividade ~1%/mês.
4. `build_scenarios` — monta os hooks e o gabarito (se `--cenarios`).
5. `generate_eventos` — mês a mês, **vetorizado com NumPy**:
   - taxa mensal por idade (curva em "U": alta em bebês e idosos) × ruído leve;
   - `Poisson(λ)` por beneficiário ativo;
   - especialidade via **Gumbel-max** com pesos de afinidade idade×sexo (`affinities.py`);
   - procedimento dentro da especialidade (peso de frequência típico + filtro de faixa
     etária — catarata só 45+, pediatria só <13, obstetrícia só mulheres 15–45…);
   - prestador (mesma região pesa 3×);
   - `valor_apresentado = custo_base × nivel_preco_prestador × lognormal(0, 0.16) × qtd`;
     glosa ~ `clip(N(0.03, 0.03), 0, 0.15)`; `valor_pago = apresentado − glosado`;
   - diagnóstico coerente com a especialidade (~62% dos eventos).
6. `generate_receitas` — por competência × plano: `ativos × PMPM_alvo × ticket_relativo ×
   reajuste_acumulado(maio) × ruído`. O `PMPM_alvo` é **calibrado** para a sinistralidade
   média-alvo do baseline (`sinistralidade_alvo = 0.75`).
7. `rebuild_aggregations` — reconstrói as tabelas `agg_*` (SQL no Postgres).

## Coerência garantida (verificável)

Pediatria → idade < 13 · Catarata → 45+ (predominante 55–79) · Obstetrícia → mulheres
15–45 · Internação `custo_medio` ≫ consulta · procedimentos complexos custam mais ·
procedimento sempre ligado à especialidade correspondente.

**v1.1**: `procedimentos.perfil_utilizacao` (pontual|recorrente|variavel) mapeado por
`grupo_procedimento` (`GRUPO_PERFIL_UTILIZACAO` em `catalogs.py`) — cirurgias/
internações/OPME/obstetrícia = pontual; consultas/exames laboratoriais/terapias/
quimioterapia = recorrente; o restante = variavel. **Coparticipação**: cada plano tem
`tem_coparticipacao`/`percentual_coparticipacao` (planos individuais/PME de entrada
cobram 10–30%; empresariais e de apartamento, em geral, não cobram); aplicada sobre
`valor_pago` só em consulta/exame/terapia/pronto_socorro (não em internação/cirurgia/OPME).

## Cenários intencionais (13) e gabarito

`k = beneficiarios / 20000` escala todos os volumes injetados. Cada cenário grava uma
linha em `cenarios_gabarito`. Os 3 procedimentos "controlados" (catarata, ressonância,
fisioterapia) têm a geração orgânica **suprimida** — só o hook os gera, para o efeito
plantado dominar o agregado.

| # | Código | O que é plantado | `efeito_esperado` | Competência-alvo |
|---|---|---|---|---|
| 1 | `s1_catarata_freq` | Jul–Ago/2026: facectomia +~100% de **frequência**, custo médio ~+3%, excedente concentrado em 3 prestadores de oftalmologia | `frequencia` (procedimento) | 2026-07 |
| 2 | `s2_internacoes` | Set–Out/2026: internações +~65%, excedente em beneficiários **60+** | `frequencia` (tipo_atendimento) | 2026-09 |
| 3 | `s3_prestador_anomalo` | Um prestador de ortopedia: custo médio ~45% acima dos pares (recebe só eventos do hook), frequência crescente em 2026, 2 procedimentos concentrados | `misto` (prestador) | 2026-06 |
| 4 | `s4_alto_custo` | ~30 beneficiários (×k) com terapias de altíssimo custo (quimio alvo, imunobiológico, hemodiálise) a partir de mar/2026 | `concentracao` (beneficiário) | 2026-06 |
| 5 | `s5_sazonalidade_resp` | Jun–Ago de **2025 e 2026**: alta de atendimentos respiratórios (repete → sazonal, não anômalo) | `sazonal` (especialidade pneumologia) | 2026-07 |
| 6 | `s6_ps_recorrente` | ~480 beneficiários (×k) com 3–5 idas ao pronto-socorro **todo mês** | `frequencia` (tipo_atendimento) | 2026-06 |
| 7 | `s7_custo_medio` | Ressonância magnética: **frequência estável** todo mês, custo médio com **degrau de +30%** a partir de jun/2026 | `custo_medio` (procedimento) | 2026-06 |
| 8 | `s8_melhora_fisioterapia` | Sessão de fisioterapia: a partir de out/2026 um programa de gestão reduz ~50% a **frequência** → despesa cai (insight positivo) | `frequencia` / redução (procedimento) | 2026-10 |
| 9 | `s9_receita_estagnada` | O reajuste anual de maio/2026 é **suprimido**: receita per capita estagna, sinistralidade sobe pelo **denominador** | `receita` | 2026-05 |
| 10 | `s10_glosa_aumenta` *(v1.1)* | Fev/2026: taxa de glosa sobe ~3,4× (despesa bruta ~estável) | `glosa` | 2026-02 |
| 11 | `s11_coparticipacao_aumenta` *(v1.1)* | Mai/2026: percentual de coparticipação sobe ~3,6× | `coparticipacao` | 2026-05 |
| 12 | `s12_glosa_copart_combinado` *(v1.1)* | Out/2026: glosa e coparticipação sobem juntas (~2,2× cada) | `misto_financeiro` | 2026-10 |
| 13 | `s13_receita_cai_mais` *(v1.1)* | Dez/2026: despesa líquida cai, mas um ajuste pontual de receita (−15%) faz a sinistralidade **piorar** | `receita` | 2026-12 |

Os 4 cenários financeiros (10–13) atuam via multiplicadores de mês (`glosa_mult_por_mes`,
`copart_mult_por_mes`, `receita_ajuste_pontual` em `generator.py`/`scenarios.py`), não
via hooks de eventos — calibrados empiricamente para que o efeito plantado supere o
ruído orgânico de despesa bruta entre meses adjacentes (que já é ±1–11% na base, mesmo
sem nenhum cenário financeiro atuando).

## Detecção (testes)

`tests/test_scenarios.py` compara a saída do motor com o gabarito — 14 asserções
cobrindo os 13 cenários (S1 tem 2: frequência e concentração em 3 prestadores).
`tests/test_cohorts.py` valida a análise de coortes (v1.1) contra os cenários S1/S8.
Ver [ANALYTICS_ENGINE.md](ANALYTICS_ENGINE.md), [V1.1.md](V1.1.md) e [DEMO.md](DEMO.md).
