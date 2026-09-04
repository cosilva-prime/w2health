# Motor analítico — W2Health Intelligence

Implementação: `backend/app/analytics/`. Primitivas puras e testáveis em `formulas.py`
(`tests/test_formulas.py`). **Toda conclusão da plataforma nasce de uma destas funções.**

Notação: `t` = mês selecionado, `0` = mês de comparação (anterior MoM, ou −12 YoY).
`D` = despesa (Σ valor_pago), `R` = receita, `N` = nº de eventos, `P = D/N` = custo médio.

## 1. Sinistralidade e séries

- `sinistralidade(D, R) = D/R × 100` (0 se `R ≤ 0`).
- `variacao_pp(a, b) = a − b` — **pontos percentuais**.
- `variacao_pct(a, b) = (a−b)/b × 100` (`None` se `b ≈ 0`).
- `acumulado_12m` = `Σ D(12) / Σ R(12) × 100`.
- Série mensal com `variacao_pp` MoM e YoY e `acumulado_12m` (`sinistralidade.serie`).

## 2. Decomposição numerador × denominador (`decomposicao_sinistralidade`)

Identidade **exata** (soma = ΔS):

```
efeito_despesa_pp = ΔD / R0 × 100
efeito_receita_pp = (D1/R1 − D1/R0) × 100
ΔS = efeito_despesa_pp + efeito_receita_pp
```

Responde "a sinistralidade subiu por gastar mais ou por arrecadar (relativamente) menos?".

## 3. Contribuição por dimensão (`contribuicoes`)

Para categorias `i` de uma dimensão: `contribuição_i = D_{i,1} − D_{i,0}`.
`participação_i = contribuição_i / ΔD_total × 100`.
**Proteção contra cancelamento**: se `|ΔD_total| < 15% · Σ|Δ|`, o denominador vira `Σ|Δ|`
(evita participações explosivas quando o líquido é pequeno mas os componentes são grandes).
Categorias novas/extintas entram naturalmente (valor 0 no outro mês).

## 4. Bridge frequência × custo médio

### Bennet (padrão — decisão aprovada, sem resíduo)

```
efeito_frequencia = (N1 − N0) · (P0 + P1) / 2
efeito_custo_medio = (P1 − P0) · (N0 + N1) / 2
efeito_frequencia + efeito_custo_medio = N1·P1 − N0·P0     (exato)
```

### Laspeyres (alternativa — `?metodo=laspeyres`)

```
efeito_frequencia = (N1 − N0) · P0
efeito_custo_medio = (P1 − P0) · N0
interacao = (N1 − N0) · (P1 − P0)          (reportada à parte)
```

### Efeito principal (`classificar_efeito`, limiar 0,65)

`|efeito_freq| / (|efeito_freq|+|efeito_custo|) ≥ 0,65` → `"frequencia"`; simétrico para
`"custo_medio"`; senão `"misto"`.

### Bridge de fator coeso (`bridge_composto`)

Para **especialidade / grupo de despesa / procedimento**, o bridge do fator é a **soma dos
bridges por procedimento** que o compõem. Isso separa corretamente *"mais procedimentos"*
(frequência, no grão do procedimento) de *"procedimento mais caro"* (custo médio) e absorve
o efeito de **mix** — sem esse cuidado, ao agregar, uma mudança de composição para
procedimentos caros apareceria como "custo médio". Demais dimensões usam o bridge por
contagem de eventos.

## 5. Concentração (`concentracao`, `gini`)

- `top_k_share[k]` = Σ dos `k` maiores / total.
- Ponto de Pareto = menor `k` com share acumulado ≥ 80%; `pareto_frac = k/n`.
- Gini via curva de Lorenz sobre a lista de valores (despesa por beneficiário ou por
  prestador). 0 = igualdade, →1 = concentração máxima.
- Frase automática: *"5% dos beneficiários concentraram X% da despesa do período."*

## 6. Anomalia de prestador (`providers`)

Grupo de pares = prestadores com a **mesma especialidade principal** no mês.
z-score de: `custo_medio`, `eventos_por_beneficiario`, `concentracao_procedimento`
(`procedimento_top_share`). **Fora do padrão** se `|z| ≥ 3` em 1 métrica **ou** `|z| ≥ 2`
em ≥ 2 métricas. `anomalia_prestadores` varre todos e ordena pelo maior `|z|`.
`ranking_variacao` ordena prestadores por `ΔD = D_prestador(t) − D_prestador(0)`.

## 7. Sazonalidade (`seasonality.classificar`)

Com ≥ 12 meses de histórico: `esperado_t = média_móvel_12m × fator_sazonal(mês)`, onde
`fator_sazonal(m) = média histórica do mês m / média geral`. Classifica pelo resíduo
padronizado `(real − esperado) / σ(resíduos históricos)`:

- `|z| ≤ 2` e `|fator_sazonal − 1| ≥ 0,15` → **`"sazonal"`** (variação esperada do mês);
- `|z| ≤ 2` e fator ~1 → `"normal"`;
- `|z| > 2` → **`"anomalo"`**.

Assim um pico de inverno que **se repete** nos dois anos é classificado como sazonal, não
anômalo.

## 8. Motor de insights (`insights.gerar`)

Percorre os resultados acima e emite insights tipados:

| tipo | dispara quando |
|---|---|
| `variacao_sinistralidade` | sempre (severidade por magnitude da ΔS) |
| `efeito_receita` | `|efeito_receita_pp| ≥ 1` e ≥ 35% da ΔS |
| `fator_dominante_especialidade` | fator de especialidade com maior `|impacto p.p.|` (+ bridge) |
| `fator_dominante_grupo` | idem por grupo de despesa |
| `internacoes` | `|Δfrequência de internações|` ≥ 8% |
| `concentracao_prestadores` | 3 maiores respondem por ≥ 25% do aumento |
| `prestador_anomalo` | há prestador fora do padrão |
| `concentracao_beneficiarios` | share dos 5% maiores (+ Gini + Pareto) |
| `reducao_despesa` | maior fator negativo (severidade "positiva") |
| `sazonalidade` | pneumologia classificada como sazonal/anômala |

Cada insight: `{severidade, emoji, titulo, descricao, metricas, deep_link {rota, params},
score, metodologia}`. **`score`** ≈ `|impacto p.p.| × pesos + |z| + share` — ordena o feed.
Nenhuma frase é fixa: os números vêm dos agregados e o texto é template preenchido; se o
banco muda, o insight muda.

## Rastreabilidade

- Toda resposta de explicação inclui o campo **`metodologia`** (a fórmula usada).
- O drill-down retorna `metodologia` = o próprio objeto `bridge` do fator.
- No frontend, cada `InsightCard` tem **"Como calculamos"** com a metodologia + as métricas.

---

## 9. Análise de coortes — "o porquê do porquê" (v1.1, Etapa A)

Módulo: `app/analytics/cohorts.py`. Um nível abaixo do bridge: para qualquer
`(dimensão, chave)`, classifica os beneficiários da célula em coortes com **identidade
exata** (sem resíduo):

```
Δdespesa = Σ(novos_carteira + novos_categoria)·despesa_atual
         + Σ(recorrentes)·Δdespesa
         − Σ(saída_carteira + permaneceram_sem_evento)·despesa_anterior
```

Cada achado carrega `tipo_evidencia` (`FATO`|`HIPOTESE`|`A_INVESTIGAR`) e
`nivel_confianca` (`ALTA`|`MEDIA`|`BAIXA`). Regra de ouro: **nunca inventar
causalidade**.

| Achado | Classificação | Regra |
|---|---|---|
| Contagens/somas diretas (quem parou de usar, quem saiu da carteira, quem trocou de prestador) | `FATO` / `ALTA` | Sempre — são dados observados |
| "Permaneceram sem evento" **e** ≥60% da despesa anterior é de procedimentos `perfil_utilizacao='pontual'` | `HIPOTESE` / `MEDIA` | Padrão compatível com conclusão de episódio pontual — nunca afirmado como certeza |
| "Permaneceram sem evento" sem esse padrão | `A_INVESTIGAR` / `BAIXA` | Sem evidência suficiente para qualquer hipótese |

`procedimentos.perfil_utilizacao` (pontual|recorrente|variavel) é mapeado por
`grupo_procedimento` no seed — só *apoia* a hipótese, nunca a prova sozinho.

Endpoint: `GET /analytics/sinistralidade/explain/{dimensao}/{chave}/causas`.

## 10. Composição financeira: bruta × líquida (v1.1, Etapa B)

Módulo: `formulas.decomposicao_financeira` + `sinistralidade.composicao`.

```
despesa_liquida = despesa_bruta − glosas − coparticipacao
sinistralidade_x = despesa_x / receita × 100          (x = bruta | liquida)
```

Decomposição de 4 efeitos — **exata**, porque despesa líquida é combinação **linear**
de bruta/glosa/coparticipação (sem termo de interação, ao contrário do bridge
frequência×custo que é multiplicativo):

```
efeito_bruta   =  ΔBruta  / R0 · 100
efeito_glosa   = −ΔGlosa  / R0 · 100
efeito_copart  = −ΔCopart / R0 · 100
efeito_receita = (Dliq1/R1 − Dliq1/R0) · 100
Σ = ΔS_líquida   (sempre exato)
```

**Convenção do MVP**: o KPI "Sinistralidade" (em toda a API/frontend) usa a base
**líquida**; a base bruta é sempre exibida ao lado, nunca omitida. Endpoint:
`GET /analytics/sinistralidade/composicao`.

## 11. Insight × Alerta (v1.1, Etapa C)

Dois módulos irmãos, nunca fundidos:

| | `insights.py` | `alerts.py` |
|---|---|---|
| Natureza | Achado automático do motor | Regra definida pelo gestor (`regras_alerta`) |
| Configurável | Não | Sim — CRUD em `/api/config/regras-alerta` |
| Catálogo | Regras fixas no código | **Catálogo fechado** de indicadores (`indicadores.py`) — `entidade × indicador × operador × limite`, sem linguagem de expressões livre |

`avaliar_regras()` calcula o indicador de verdade e só emite alerta quando o valor
cruza o limite — nunca um alerta fabricado. Indicadores cobrem beneficiário, prestador,
procedimento, plano e financeiro (glosa/coparticipação); `contrato` fica limitado a
despesa/participação/vidas (sinistralidade por contrato exige receita própria, fora do
escopo sem o módulo de reajuste — ver `EVOLUCAO_FEEDBACK_ESPECIALISTA.md`).
