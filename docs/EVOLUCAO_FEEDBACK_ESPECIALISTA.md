# W2Health Intelligence — Evolução Pós-Feedback Especialista

> **Status: Evoluções 1 e 3 implementadas na íntegra; Evolução 4 implementada; Evolução
> 2 (reajuste contratual) NÃO implementada — permanece só como análise nesta página,
> por decisão explícita do usuário ao aprovar a v1.1.** Ver o resultado da implementação
> em [V1.1.md](V1.1.md). Este documento é preservado como registro da análise original
> e como referência para um futuro discovery do módulo de reajuste.
> Data da análise: 2026-09-03 · Data da implementação (v1.1): 2026-09-04

---

## 1. Resumo executivo

O consultor validou a tese central do produto (indicador → variação → causa → impacto →
onde investigar) e trouxe quatro pedidos de evolução, todos no mesmo espírito: **ir um
nível mais fundo na explicação**, sem transformar o MVP em outra coisa.

As quatro evoluções são **aditivas** ao que já existe — nenhuma delas exige remover ou
redesenhar telas, tabelas ou endpoints atuais. O maior risco real não é técnico, é de
**escopo**: as Evoluções 2 e 4 introduzem, pela primeira vez no produto, telas de
configuração com escrita (CRUD), o que rompe a premissa atual de "produto 100%
leitura, sem autenticação". Isso está sinalizado explicitamente na seção 10 e deve ser
uma decisão consciente sua, não um efeito colateral.

**Recomendação resumida** (detalhada na seção 17): implementar primeiro a **Evolução 1**
(explicação em múltiplos níveis) e a **Evolução 3 – Fase A** (despesa bruta × líquida),
que aprofundam a explicação sem introduzir escrita/CRUD. Deixar **Evolução 4** e depois
**Evolução 2** para uma etapa seguinte, quando autenticação básica entrar em pauta.

---

## 2. Situação atual (o que já existe e sustenta as evoluções)

| Camada | Estado atual relevante |
|---|---|
| **Modelo de dados** | 17 tabelas. `eventos_assistenciais` tem `valor_apresentado`, `valor_glosado`, `valor_pago` (= apresentado − glosado). **Não existe coparticipação.** `receitas` tem grão **competência × plano** (não por contrato). `contratos` só tem `id_plano`, `nome`, `tipo` — sem meta, reajuste ou data-base. `beneficiarios` já tem `data_adesao`/`data_saida`/`status` (dá para saber quem saiu da carteira). |
| **Camada analítica** | `agg_sinistralidade_competencia` (executivo), `agg_competencia_dimensao` (9 dimensões: grupo_despesa, tipo_atendimento, especialidade, procedimento, prestador, regiao, faixa_etaria, sexo, **plano** — **`contrato` não existe como dimensão hoje**), `agg_prestador_competencia`, `agg_beneficiario_competencia`. |
| **Motor analítico** | `formulas.py` (bennet/laspeyres, contribuição, concentração, gini) · `decomposition.py` (`explicar` + `drill`, com bridge composto por procedimento para especialidade/grupo/procedimento) · `providers.py` (z-score vs pares) · `seasonality.py` · `insights.py` (10 regras fixas, sem persistência, sem distinção insight/alerta). |
| **API** | 100% leitura (`GET`). Nenhum endpoint de escrita existe hoje. |
| **Frontend** | 6 rotas, todas leitura/navegação. Nenhuma tela de configuração/CRUD. |
| **Dados sintéticos** | 20k beneficiários, 9 cenários plantados com gabarito, testados (`tests/test_scenarios.py`, 10/10 verdes). |

Essas lacunas específicas (sem coparticipação, sem `contrato` como dimensão, sem
persistência de configuração, sem camada causal abaixo do bridge) são exatamente o que
as quatro evoluções pedem para preencher — não há retrabalho, só extensão.

---

## 3. Feedback recebido (síntese)

1. O motor explica **o que** mudou financeiramente, mas não **por que** o comportamento
   assistencial aconteceu — falta uma camada causal/descritiva com cohortes de
   beneficiários, distinguindo fato de hipótese.
2. Falta uma visão de **reajuste contratual** ligada à sinistralidade por contrato, com
   simulação (não fórmula fixa).
3. A despesa deveria ser vista em camadas — **bruta → glosas → coparticipação → líquida**
   — e essa composição deveria entrar na árvore explicativa.
4. Falta uma tela de **configuração de insights/alertas**, com separação conceitual clara
   entre insight automático (achado do motor) e alerta configurado (regra do usuário).

---

## 4. Evolução 1 — Explicação em múltiplos níveis (o "porquê do porquê")

### 4.1 O que construir

Uma **camada causal-descritiva** sobre qualquer fator já identificado pelo `explicar`/
`drill` atuais — não um recurso novo e isolado, e sim **mais um nível da mesma árvore**:

```
Sinistralidade ↓
  → fator (ex.: Cardiologia, −R$ 800 mil)          [já existe: explicar()]
    → bridge frequência × custo médio               [já existe: drill()]
      → COORTES de beneficiários (NOVO)
        → cada beneficiário / evento                [já existe: onde_investigar]
```

### 4.2 Análise de coortes — identidade exata (mesmo princípio do Bennet)

Para qualquer par (dimensão, chave) e dois meses, sejam **B0** = beneficiários com
despesa>0 naquela célula no mês anterior e **B1** = idem no mês atual. A variação da
despesa do fator se decompõe **exatamente**, sem resíduo:

```
Δdespesa = Σ_{B1\B0} despesa_atual                                    "novos usuários"
         + (Σ_{B0∩B1} despesa_atual − Σ_{B0∩B1} despesa_anterior)     "recorrentes: variação"
         − Σ_{B0\B1} despesa_anterior                                 "deixaram de utilizar"
```

O terceiro termo ("deixaram de utilizar") é então sub-classificado, usando campos que
**já existem** em `beneficiarios` (`status`, `data_saida`):

- **saíram da carteira** (`status='inativo'` ou `data_saida` ≤ mês atual);
- **permaneceram na carteira sem novo evento** — aqui mora a diferença entre FATO e
  HIPÓTESE pedida pelo consultor.

### 4.3 Fato vs. Hipótese vs. A investigar — regras explícitas (sem inventar causalidade)

| Classificação | Regra objetiva | Exemplo |
|---|---|---|
| **Fato** | Contagem/soma direta de dados observados | *"35 beneficiários com evento em Cardiologia no mês anterior não tiveram novo evento este mês."* |
| **Fato** | `status`/`data_saida` do beneficiário | *"12 desses 35 saíram da carteira."* |
| **Fato** | Prestador do evento mudou entre os 2 meses para o mesmo beneficiário (comparável via `eventos_assistenciais`) | *"8 beneficiários recorrentes trocaram de prestador."* |
| **Hipótese (confiança média)** | Só quando ≥3 meses consecutivos de utilização terminam no mês anterior **e** o procedimento predominante é de perfil "pontual" (cirurgia/internação/OPME) | *"Padrão compatível com conclusão de tratamento — a confirmar."* |
| **A investigar (confiança baixa)** | Quando nenhuma regra acima se aplica | *"Sem padrão identificável nos dados — recomenda-se investigação manual."* |

Nunca se afirma "o tratamento foi encerrado" como fato — apenas como hipótese rotulada,
com o dado de suporte explícito. Isso exige **1 coluna nova**: `procedimentos.
perfil_utilizacao` ('pontual' | 'recorrente' | 'variavel'), derivada do
`grupo_procedimento` já existente (mapeamento simples no catálogo).

### 4.4 Genericidade (não é uma regra só para Cardiologia)

O motor recebe **(dimensão, chave, competência, comparação)** — os mesmos parâmetros que
`drill()` já recebe hoje — e funciona identicamente para especialidade, procedimento,
prestador, tipo de atendimento e (após a seção 4.5) contrato. O beneficiário é sempre a
folha da árvore (já coberto pela tela de detalhe existente).

### 4.5 Pré-requisito: adicionar `contrato` como dimensão

Hoje `contrato` não é uma dimensão do motor (só `plano` é). Para "por contrato" fazer
sentido nas coortes (e na Evolução 2), é preciso adicioná-la em 3 lugares que já seguem
o mesmo padrão das dimensões existentes: `agg_competencia_dimensao` (SQL de agregação em
`aggregate.py`), `DIMENSOES_VALIDAS` (`decomposition.py`) — como dimensão de **contagem
de eventos** (não coesa como especialidade/procedimento, pois um contrato mistura várias
especialidades).

### 4.6 Novo endpoint e tela

- `GET /api/analytics/sinistralidade/explain/{dimensao}/{chave}/causas?competencia=&comparacao=`
  — não substitui `/explain/{dimensao}/{chave}` atual, é um nível adicional.
- Frontend: seção expansível **"Por que [Cardiologia] caiu?"** dentro do painel de drill
  já existente na tela Sinistralidade — mesma página, sem nova rota.

### 4.7 Risco de performance

As coortes são calculadas sob demanda (consulta pontual em `eventos_assistenciais`,
filtrada por competência + dimensão + chave, mesmos índices já usados por
`eventos_da_categoria`). **Não** proponho materializar isso em uma nova tabela agora — o
drill-down é um caminho de baixa frequência de acesso (diferente do dashboard
executivo), então a consulta sob demanda é adequada. Se no futuro isso ficar lento com
100k beneficiários, o caminho de otimização é uma tabela `agg_beneficiario_dimensao_
competencia`, mas isso multiplicaria a maior tabela de agregação por ~9× — não recomendo
como ponto de partida.

**Complexidade: Média-Alta.**

---

## 5. Evolução 2 — Reajuste contratual baseado em sinistralidade

### 5.1 Lacuna real descoberta na análise

`receitas` é gerada por **competência × plano**, não por **competência × contrato**. Hoje
vários contratos *poderiam* compartilhar um plano (o modelo permite N:1), mas a receita
só existe no nível do plano. Para uma visão "sinistralidade por contrato" de verdade
(despesa por contrato já é possível via join beneficiário→contrato, mas receita não), é
necessário **gerar receita no grão de contrato**.

Proposta: nova tabela `receitas_contrato` (competência, id_contrato, quantidade_
beneficiarios, receita_contraprestacao, reajuste_aplicado_no_periodo) **coexistindo** com
`receitas` (que continua servindo relatórios por plano) — sem quebrar nada existente.

### 5.2 Motor de simulação (parametrizável, não uma fórmula única)

Como pedido explicitamente, **não fixamos uma fórmula de reajuste**. Proposta de 2 novas
tabelas de configuração:

- **`contrato_parametros_reajuste`**: `id_contrato`, `data_base`, `indice_referencia`
  (texto livre, ex. "IPCA", "VCMH"), `meta_sinistralidade`, `metodologia` (enum:
  `sinistralidade_meta` | `indice_referencia` | `hibrido` | `personalizado`),
  `parametros_extra` (JSON — pesos, limites min/máx, carência), `ativo`.
- **`contrato_reajuste_historico`**: registro do que foi de fato aplicado em cada
  data-base (auditoria/backtesting).

O **motor** (`app/analytics/reajuste.py`) oferece estratégias plugáveis:

| Metodologia | Cálculo |
|---|---|
| `sinistralidade_meta` | reajuste sugerido = (sinistralidade_apurada / meta) − 1, projetando despesa constante |
| `indice_referencia` | reajuste = índice informado manualmente (passthrough) |
| `hibrido` | média ponderada das duas anteriores (peso configurável) |
| `personalizado` | gestor digita % livremente só para simular |

`simular(id_contrato, reajuste_pct, premissas?)` retorna sinistralidade e receita
projetadas — **é uma calculadora de "e se", não uma decisão automatizada**, conforme
pedido. Crescimento vegetativo da despesa é um parâmetro explícito (default 0%), nunca
um modelo preditivo inventado.

### 5.3 Endpoints

```
GET  /api/analytics/contratos                              lista com vidas, receita, despesa,
                                                             sinistralidade atual/acumulada,
                                                             reajuste atual, meta, data-base
GET  /api/analytics/contratos/{id}                          detalhe + série histórica
GET  /api/analytics/contratos/{id}/simular-reajuste?pct=... simulação (somente leitura/computa)
POST /api/config/contratos/{id}/parametros-reajuste         ⚠️ primeira escrita real do produto
```

### 5.4 Tela nova

`/contratos` (lista) e `/contratos/[id]` (detalhe + simulador: input de % de reajuste →
sinistralidade projetada atualizada ao vivo, mesmo padrão visual das demais telas).

**Complexidade: Alta** — é a evolução mais cara: 3 tabelas novas, motor de simulação,
2 telas, e a primeira tela administrativa/CRUD do produto.

---

## 6. Evolução 3 — Despesa bruta × líquida (glosa + coparticipação)

### 6.1 O que falta no modelo

`valor_pago` hoje já é "bruto − glosa", mas é tratado como *a* despesa em todo o motor.
**Coparticipação não existe no modelo.** Ela precisa ser adicionada e subtraída para
chegar à "despesa líquida" que o consultor descreve.

Migration aditiva (sem quebrar nada):
- `eventos_assistenciais.valor_coparticipacao` (Numeric, default 0);
- `planos.tem_coparticipacao` (bool) + `planos.percentual_coparticipacao` (float) — para
  o gerador sintético decidir quando e quanto aplicar por evento.

### 6.2 Decomposição de 4 componentes — extensão natural da fórmula já existente

A decomposição atual (`decomposicao_sinistralidade`) já separa efeito-despesa de
efeito-receita com identidade exata. Proponho estendê-la (nova função, a atual
**permanece intacta** para não quebrar nenhuma tela hoje) para 4 termos, na mesma lógica
de substituição sequencial (ordem fixa e documentada, como já é prática no motor):

```
efeito_bruta   = ΔBruta / R0              × 100
efeito_glosa   = −ΔGlosa / R0             × 100
efeito_copart  = −ΔCoparticipação / R0    × 100
efeito_receita = (Dliq1/R1 − Dliq1/R0)    × 100
Σ = ΔS_líquida   (exato)
```

### 6.3 Compatibilidade com o que já existe (decisão importante)

**Por padrão, todas as telas e endpoints atuais continuam calculando "despesa" exatamente
como hoje** (bruto − glosa, sem coparticipação) — os números que a diretoria já viu na
demonstração não mudam. A visão bruta/líquida entra como **card adicional** ("Composição
da despesa assistencial") na Visão Executiva e em Sinistralidade, não como substituição
do KPI principal. Isso evita o risco de confundir números já validados.

Fase A (recomendada agora): adicionar bruta/glosa/coparticipação/líquida só em
`agg_sinistralidade_competencia` (nível executivo) + 1 novo endpoint
`GET /analytics/sinistralidade/composicao`. Fase B (mais cara, proponho depois): propagar
essas colunas para as demais tabelas `agg_*` para que o bridge por fator também separe
glosa/coparticipação — não apliquei o bridge frequência×custo a glosa/coparticipação
porque elas não são "eventos" com frequência própria; proponho tratá-las como taxas
médias (% de glosa, % de coparticipação), evitando forçar uma métrica que não tem
significado clínico ali.

### 6.4 Cenários sintéticos A–D (conforme pedido)

| Cenário | O que muda nos dados | O que o motor deve mostrar |
|---|---|---|
| A | Taxa de glosa sobe para um grupo de prestadores/procedimentos por alguns meses | despesa líquida cai apesar da bruta estável, efeito atribuído a glosa |
| B | Percentual de coparticipação de um plano sobe a partir de um mês | despesa líquida (operadora) cai, efeito atribuído a coparticipação |
| C | Combinação moderada de A+B | bruta ~estável, líquida cai — efeito misto glosa+coparticipação |
| D | Despesa cai, mas receita cai mais (reaproveita a lógica do cenário `s9` já existente) | sinistralidade piora mesmo com despesa em queda — efeito receita dominante |

Cada um ganha entrada no `cenarios_gabarito` e teste em `test_scenarios.py`, seguindo
exatamente o padrão dos 9 cenários atuais.

**Complexidade: Média (Fase A) / Alta (Fase B).**

---

## 7. Evolução 4 — Configuração de Insights e Alertas

### 7.1 Separação conceitual (implementada, não só documentada)

- **Insight** (`app/analytics/insights.py`, já existe): achado automático, sem
  configuração do usuário.
- **Alerta** (novo, `app/analytics/alerts.py`): regra explícita, configurada pelo
  usuário, avaliada contra os dados. São dataclasses e módulos **distintos**; a UI mostra
  os dois lado a lado com identidade visual diferente (💡 Insight vs 🔔 Alerta), nunca
  misturados na mesma lista.

### 7.2 Modelo genérico de regra (sem motor de fórmulas livres)

Nova tabela `regras_alerta`: `entidade` (beneficiario|prestador|procedimento|contrato|
glosa_coparticipacao), `indicador` (chave controlada, ex. `participacao_variacao`,
`crescimento_despesa_pct`, `custo_medio_vs_pares_pct`, `sinistralidade_pct`,
`variacao_pp`, `vidas_minimas`, `dias_para_data_base`, `variacao_glosa_pct`), `operador`
(`>=`,`>`,`<=`,`<`,`==`), `limite`, `severidade` (`critica`|`atencao`|`informativo`),
`escopo` (JSON opcional, ex. restringir a 1 contrato), `ativo`.

**Decisão de escopo deliberada**: em vez de uma linguagem de expressões livre (risco de
segurança e complexidade alta para o estágio atual), os indicadores são um **catálogo
fechado e explícito no código** (`app/analytics/indicadores.py`), cada um com uma
função `(session, competência, comparação, escopo) → valores`. A genericidade pedida
pelo consultor vem da combinatória **entidade × indicador × operador × limite**, que já
cobre todos os exemplos dados (beneficiário, prestador, procedimento, contrato, glosa/
coparticipação). Um motor de expressões livres fica como evolução futura, se necessário.

### 7.3 Endpoints

```
GET    /api/config/indicadores              catálogo de indicadores disponíveis (alimenta o form)
GET    /api/config/regras-alerta
POST   /api/config/regras-alerta            ⚠️ segunda escrita real do produto
PUT    /api/config/regras-alerta/{id}
DELETE /api/config/regras-alerta/{id}
GET    /api/analytics/alertas?competencia=&comparacao=
```

### 7.4 Telas

`/configuracao/insights` (nova — lista + formulário de regra, dropdowns em cascata
entidade→indicador→operador) e uma aba **"Alertas configurados"** dentro da tela
`/insights` existente, ao lado do feed de insights automáticos.

**Complexidade: Média-Alta.**

---

## 8. Impacto no modelo de dados (consolidado)

Todas as mudanças são **aditivas** — nenhuma coluna/tabela removida ou renomeada.

| # | Mudança | Evolução |
|---|---|---|
| 1 | `procedimentos.perfil_utilizacao` | 1 |
| 2 | `contrato` entra como dimensão do motor (sem migration — é join) | 1, 2 |
| 3 | `receitas_contrato`, `contrato_parametros_reajuste`, `contrato_reajuste_historico` | 2 |
| 4 | `eventos_assistenciais.valor_coparticipacao`; `planos.tem_coparticipacao`, `planos.percentual_coparticipacao` | 3 |
| 5 | `agg_sinistralidade_competencia`: colunas `despesa_bruta`, `glosas`, `coparticipacao`, `despesa_liquida` | 3 |
| 6 | `regras_alerta` | 4 |

Cada linha é uma migration independente — podem ser aplicadas e revertidas isoladamente.

## 9. Impacto no motor analítico

Novos módulos, seguindo exatamente a organização atual de `app/analytics/`:

- `cohorts.py` (Evolução 1) · `reajuste.py` (Evolução 2) · extensão de `sinistralidade.py`
  ou novo `composicao.py` (Evolução 3) · `alerts.py` + `indicadores.py` (Evolução 4).
- `decomposition.py`: adicionar `"contrato"` a `DIMENSOES_VALIDAS` (não a
  `DIMENSOES_COESAS`).
- `insights.py`: **não muda de responsabilidade** — continua só gerando insights; a
  distinção com alertas é feita por módulo separado, não por flag dentro do mesmo código.

## 10. Impacto na arquitetura

Nenhuma mudança de stack. Mesma estrutura em camadas. **Ponto de atenção real**: hoje a
API é 100% leitura e sem autenticação (decisão registrada do MVP). As Evoluções 2 e 4
introduzem os **primeiros endpoints de escrita** do produto (parâmetros de reajuste,
regras de alerta). Recomendo:
- Usar esquemas Pydantic reais (`app/schemas/`) para validar os corpos dessas requisições
  — até aqui os endpoints devolvem `dict` livre; para escrita isso deixa de ser
  aceitável.
- Decidir explicitamente, antes de construir essas duas evoluções, se o MVP continua sem
  autenticação (aceitável para demonstração, mas registrar como dívida antes de uso real
  — ver `docs/DECISOES-MVP.md`).

## 11. Novas telas

| Tela | Rota | Evolução |
|---|---|---|
| Seção "Por que [fator] caiu/subiu?" (dentro do drill existente) | `/sinistralidade` (mesma rota) | 1 |
| Lista de contratos | `/contratos` | 2 |
| Detalhe de contrato + simulador de reajuste | `/contratos/[id]` | 2 |
| Card "Composição da despesa assistencial" | `/` e `/sinistralidade` (mesmas rotas) | 3 |
| Configuração de insights/alertas | `/configuracao/insights` | 4 |
| Aba "Alertas configurados" | `/insights` (mesma rota) | 4 |

Sidebar ganha 2 itens novos: **Contratos** e **Configuração**.

## 12. Novos endpoints (consolidado)

```
GET    /api/analytics/sinistralidade/explain/{dimensao}/{chave}/causas
GET    /api/analytics/sinistralidade/composicao
GET    /api/analytics/contratos
GET    /api/analytics/contratos/{id}
GET    /api/analytics/contratos/{id}/simular-reajuste
POST   /api/config/contratos/{id}/parametros-reajuste
GET    /api/config/indicadores
GET    /api/config/regras-alerta
POST   /api/config/regras-alerta
PUT    /api/config/regras-alerta/{id}
DELETE /api/config/regras-alerta/{id}
GET    /api/analytics/alertas
```

## 13. Evolução da massa sintética

- `catalogs.py`: mapear `perfil_utilizacao` por `grupo_procedimento`; parâmetros de
  coparticipação por plano.
- `generator.py`: aplicar coparticipação por evento conforme o plano do beneficiário.
- `scenarios.py`: 4 novos cenários (A–D da seção 6.4) + parâmetros de reajuste plausíveis
  por contrato (data-base espalhada no ano, meta ~70–80%).
- `aggregate.py`: novas colunas agregadas (bruta/glosa/coparticipação/líquida).

## 14. Estratégia de testes

- `test_formulas.py`: identidade exata da decomposição de 4 componentes e da soma das
  coortes — mesmo padrão dos testes de Bennet já existentes.
- `test_scenarios.py`: 4 novos testes (cenários A–D) + reaproveitamento do cenário `s8`
  (fisioterapia) para validar que a coorte aponta predominantemente "beneficiários sem
  nova utilização" (é um cenário de frequência, população estável).
- `test_api.py`: novos endpoints.
- **Condição de aceite por etapa**: a suíte atual (52 testes) deve continuar 100% verde
  após cada evolução — nenhuma delas deve alterar o comportamento hoje observável.

## 15. Riscos técnicos

1. Performance de coortes sob demanda em bases maiores — mitigado (ver 4.7); revisitar
   se `--beneficiarios 100000` se mostrar lento na prática.
2. Escrita sem autenticação (Evoluções 2 e 4) — aceitável para demo, deve ser registrado
   como dívida explícita antes de qualquer uso real (ver seção 10).
3. "Despesa líquida" pode ser mal-entendida se não ficar clara a diferença para a
   "despesa" que a diretoria já viu — mitigado mantendo o KPI atual intocado por padrão
   (seção 6.3).
4. Decomposição de 4 termos não comuta perfeitamente entre bruta/glosa/coparticipação —
   mitigado fixando e documentando a ordem (mesma transparência já praticada no motor).
5. Motor de reajuste pode ser lido como recomendação automática — mitigar com texto
   explícito na UI ("simulação, não decisão").

## 16. Priorização recomendada

| Ordem | Evolução | Por quê |
|---|---|---|
| 1 | **Evolução 1** — múltiplos níveis / coortes | Maior valor para a tese central; nenhuma escrita/CRUD; reaproveita 100% da infraestrutura de `explain`/`drill`. |
| 2 | **Evolução 3 – Fase A** — bruta × líquida | Mudança de modelo pequena e isolada (1 coluna + 2 no plano); alto valor analítico; prepara terreno de dados para a Evolução 2. |
| 3 | **Evolução 4** — configuração de insights/alertas | Introduz CRUD de forma controlada, sem mexer em receita/contrato; risco mais contido que a Evolução 2. |
| 4 | **Evolução 2** — reajuste contratual | Maior complexidade; novo domínio de negócio inteiro; reaproveita a dimensão `contrato` já introduzida na Evolução 1. |

## 17. Estimativa de complexidade

| Evolução | Complexidade |
|---|---|
| 1 — Explicação em múltiplos níveis | **Média-Alta** |
| 2 — Reajuste contratual | **Alta** |
| 3 — Bruta × líquida (Fase A / Fase B) | **Média** / **Alta** |
| 4 — Configuração de insights e alertas | **Média-Alta** |

## Recomendação para a próxima versão do MVP

Proponho uma **v1.1** contendo apenas **Evolução 1** + **Evolução 3 (Fase A)**. As duas
aprofundam exatamente o que o consultor pediu de mais valioso — o "porquê do porquê" e a
composição real da despesa — **sem introduzir escrita, CRUD ou qualquer necessidade de
autenticação**, mantendo o produto no mesmo espírito de baixo risco que ele tem hoje.
**Evolução 4** e **Evolução 2** ficariam para uma **v1.2**, quando fizer sentido discutir
autenticação básica — pré-requisito real antes de qualquer tela de configuração ir a
campo com usuários de verdade.

---

*Aguardando aprovação para iniciar a implementação. Nenhuma alteração de código foi feita
a partir deste ponto.*
