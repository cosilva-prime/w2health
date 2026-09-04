# Modelo de dados — W2Health Intelligence

Fonte de verdade: `backend/app/models/`. Migrations: `backend/alembic/versions/`.

## Camada fonte (OLTP-like)

### `regioes`
`id`, `cidade`, `uf`, `macrorregiao`

### `planos`
`id`, `codigo` (único), `nome`, `segmentacao` (ambulatorial|hospitalar|completo),
`ticket_medio_base`, `tem_coparticipacao` (bool, v1.1), `percentual_coparticipacao`
(v1.1 — aplicado sobre `valor_pago` em consulta/exame/terapia/pronto_socorro; não incide
em internação/cirurgia/OPME)

### `contratos`
`id`, `id_plano→planos`, `nome`, `tipo` (PF|PME|Empresarial)

### `especialidades`
`id`, `codigo` (único), `nome`, `grupo` (clinica|cirurgica|diagnostico|terapia)

### `procedimentos`
`id`, `codigo` (único), `descricao`, `id_especialidade→especialidades`,
`grupo_procedimento`, `complexidade` (1–5), `custo_base`, `tipo_atendimento_tipico`,
`idade_min`, `idade_max`, `perfil_utilizacao` (v1.1 — pontual|recorrente|variavel,
mapeado por `grupo_procedimento`; apoia a classificação de hipóteses na análise de
coortes, nunca usado sozinho para afirmar causalidade)

### `prestadores`
`id`, `nome_ficticio`, `tipo_prestador` (hospital|clinica|laboratorio|pronto_atendimento|
consultorio), `id_regiao→regioes`, `id_especialidade_principal→especialidades`,
`nivel_preco` (multiplicador interno de preço, não exposto)

### `diagnosticos`
`id`, `cid` (fictício, único), `descricao`, `id_especialidade→especialidades` (nullable)

### `competencias`
`competencia` (PK, 1º dia do mês), `ano`, `mes`, `mes_nome`, `trimestre`, `is_inverno`

### `beneficiarios`
`id`, `codigo` (`BEN-000001`, único), `sexo` (M|F), `data_nascimento`, `faixa_etaria`,
`id_regiao`, `id_plano`, `id_contrato`, `data_adesao`, `data_saida` (nullable), `status`
(ativo|inativo)

### `receitas`  — grão: competência × plano
`id`, `competencia`, `id_plano→planos`, `quantidade_beneficiarios`,
`receita_contraprestacao`. Único: (`competencia`, `id_plano`).

### `eventos_assistenciais`  — grão: 1 linha por atendimento/procedimento
`id` (bigint), `id_beneficiario`, `id_prestador`, `id_procedimento`, `id_especialidade`,
`id_diagnostico` (nullable), `id_regiao`, `data_evento`, `competencia`, `tipo_atendimento`
(consulta|exame|terapia|pronto_socorro|internacao|cirurgia|opme), `quantidade`,
`valor_apresentado`, `valor_glosado`, `valor_pago`, `valor_coparticipacao` (v1.1),
`cenario_tag` (nullable — rótulo do cenário sintético que injetou/alterou a linha; só
QA/testes).

Semântica financeira (v1.1 — ver [V1.1.md](V1.1.md) § Etapa B):
```
valor_apresentado    = despesa BRUTA apresentada pelo prestador
valor_glosado        = parcela glosada (não paga ao prestador)
valor_pago           = valor_apresentado − valor_glosado          (existente, inalterado)
valor_coparticipacao = parcela de valor_pago cobrada do beneficiário
despesa líquida (calculada, não persistida por evento)
    = valor_apresentado − valor_glosado − valor_coparticipacao
```
**Despesa assistencial bruta = Σ valor_apresentado. Despesa líquida (KPI oficial do
MVP) = Σ (valor_apresentado − valor_glosado − valor_coparticipacao).**

Índices: `competencia`; compostos `(competencia, id_especialidade|id_prestador|
id_procedimento|tipo_atendimento)`; FKs individuais; `cenario_tag`.

## Camada analítica (materializada pós-seed)

### `agg_sinistralidade_competencia`  — PK `competencia`
`receita`, `beneficiarios_ativos`,
`exposicao_beneficiario_mes` (= Σ `quantidade_beneficiarios` das receitas do mês),
`eventos`, `custo_pmpm`, `receita_media_beneficiario`.
**v1.1**: `despesa_bruta` (Σ apresentado), `glosas` (Σ glosado), `coparticipacao`
(Σ coparticipação), `despesa_liquida` (= bruta − glosas − coparticipacao),
`sinistralidade_bruta`, `sinistralidade_liquida` (%). Não há mais colunas soltas
`despesa`/`sinistralidade` no banco — as consultas em `analytics_repo.py` expõem
`despesa_liquida`/`sinistralidade_liquida` também sob os aliases `despesa`/
`sinistralidade` (convenção oficial do MVP), sem duplicar dado.

### `agg_competencia_dimensao`  — único (`competencia`, `dimensao`, `chave`)
`dimensao` ∈ {grupo_despesa, tipo_atendimento, especialidade, procedimento, prestador,
regiao, faixa_etaria, sexo, plano, **contrato** (v1.1)}. `chave` (id ou valor categórico), `rotulo`,
`despesa`, `eventos`, `quantidade`, `beneficiarios`, `custo_medio` (= despesa/eventos),
`freq_por_mil` (= eventos / exposição × 1000). Índices em `competencia` e `dimensao`.
`despesa` aqui é sempre **Σ valor_pago** (bruta − glosa, sem coparticipação) — o efeito
glosa/coparticipação só é decomposto no nível executivo (`agg_sinistralidade_competencia`
+ `/analytics/sinistralidade/composicao`), não propagado ao bridge por dimensão (ver
[V1.1.md](V1.1.md) § Limitações — "Fase B" fica para uma versão futura).

### `agg_prestador_competencia`  — único (`competencia`, `id_prestador`)
`despesa`, `eventos`, `beneficiarios`, `custo_medio`, `participacao` (fração da despesa do
mês), `procedimento_top_id`, `procedimento_top_share`

### `agg_beneficiario_competencia`  — único (`competencia`, `id_beneficiario`)
`despesa`, `eventos`

### `cenarios_gabarito`
`id`, `codigo` (único, ex. `s1_catarata_freq`), `nome`, `competencia_alvo`, `dimensao`,
`chave_alvo`, `rotulo_alvo`, `efeito_esperado` (frequencia|custo_medio|misto|sazonal|
concentracao|receita), `descricao`, `params` (JSON). Consumido pelos testes de integração.

### `seed_manifest`
`id`, `seed`, `beneficiarios`, `inicio`, `fim`, `escala_eventos`, `criado_em`,
`contagens` (JSON: eventos, competências, cenários, contagens das `agg_*`).

## Configuração (v1.1)

### `regras_alerta`
`id`, `nome`, `entidade` (beneficiario|prestador|procedimento|plano|contrato|financeiro),
`indicador` (chave do catálogo fechado — `app/analytics/indicadores.py`), `operador`
(>=|>|<=|<|==), `limite`, `severidade` (critica|atencao|informativo), `escopo` (JSON,
opcional), `ativo`, `criado_em`, `atualizado_em`. Único dado **configurável pelo
usuário** no produto — preservado entre reseeds da massa sintética (o seed só insere 3
regras de exemplo se a tabela estiver vazia). ⚠️ Endpoints de escrita sem autenticação —
ver [V1.1.md](V1.1.md) § Dívida Técnica.

## Faixas etárias (bandas de saúde)

`0-1, 2-4, 5-9, 10-14, 15-19, 20-29, 30-39, 40-49, 50-59, 60-69, 70-79, 80+`
(`app/core/faixas.py`). Gravada em `beneficiarios.faixa_etaria` no momento do seed
(não recalculada por competência no MVP — aproximação documentada).

## Notas de precisão

Valores monetários: `Numeric(14,2)` no banco; o motor converte para `float` na leitura
(aceitável para a demonstração). A soma dos efeitos do bridge de Bennet é exata em
aritmética real; arredondamentos de exibição usam 2 casas.
