# W2Health Intelligence — Discovery Pós-Feedback de Gestão em Saúde

> **Status: documento de análise. Nenhuma linha de código, migration, tela ou endpoint
> foi criada a partir deste discovery.** Ele consolida o segundo feedback (gestor de
> saúde), cruza com o primeiro (consultor especialista, ver
> [EVOLUCAO_FEEDBACK_ESPECIALISTA.md](EVOLUCAO_FEEDBACK_ESPECIALISTA.md)) e propõe uma
> priorização. As análises anteriores permanecem válidas — este texto as estende, não as
> substitui.
> Data da análise: 2026-09-09 · Base de código de referência: v1.1 (81 testes verdes)

## Convenção de evidência (usada em todo o documento)

| Selo | Significado |
|---|---|
| `[F1]` | Pedido explicitamente pelo consultor especialista (feedback 1) |
| `[F2]` | Pedido explicitamente pelo gestor de saúde (feedback 2) |
| `[INFERÊNCIA]` | Conclusão nossa a partir do código/modelo — não dita por nenhum feedback |
| `[HIPÓTESE]` | Hipótese de produto — ideia plausível, ainda não validada por ninguém |
| `[EXIGE VALIDAÇÃO]` | Só entra no produto após confirmação de um profissional de operadora |

Dois profissionais tocando no mesmo tema **aumenta a confiança de que o tema importa**;
não é validação de mercado. Nenhuma frase deste documento afirma "o mercado precisa
disso".

---

## 1. Resumo executivo

O segundo feedback não muda a tese do W2Health (indicador → variação → causa → impacto →
onde investigar → decisão). Ele **desloca o eixo da explicação**: o primeiro feedback
pediu para descer mais fundo na *causa assistencial* ("por que Cardiologia caiu?"); o
segundo pede para amarrar essa causa a uma *estrutura financeira e contratual* ("quem
está provocando isso, sob qual contrato, e qual a relação com a receita?").

Os dois convergem em um ponto central: **o beneficiário e o contrato deixam de ser folhas
de um drill-down e passam a ser dimensões de primeira classe da explicação.** O W2Health
já tem quase toda a infraestrutura de *despesa* para isso (coortes, concentração, Gini,
dimensão `contrato`, decomposição financeira). O que falta, de verdade, é o **lado da
receita** — e é aí que mora a maior incerteza de dados.

Três blocos de trabalho aparecem, em ordem crescente de risco:

1. **Baixo risco, alto valor, sem novos dados** — propagar a composição financeira
   (bruta/glosa/coparticipação/líquida) e a análise de concentração/coortes para os
   níveis de contrato e beneficiário; trazer a concentração de beneficiários para o topo
   da árvore de explicação. Isso é engenharia sobre dados que já existem.
2. **Médio risco — depende de assumir uma fonte de receita mais granular** — receita por
   contrato (`sinistralidade por contrato` de verdade) e receita *atribuída* por
   beneficiário (rateio). Exige decisão de produto sobre metodologia e nomenclatura, e
   validação de que a fonte existe no cliente real.
3. **Alto risco — exige discovery próprio antes de qualquer código** — módulo de
   reajuste contratual e previsibilidade/projeção. Ambos reforçados pelos dois feedbacks,
   ambos com regra de negócio ainda desconhecida.

Recomendação: executar o bloco 1 como uma **v1.2** enxuta, rodar o discovery de receita
granular em paralelo (bloco 2), e tratar reajuste e previsibilidade como **trilhas de
discovery independentes** (bloco 3), sem prometer implementação.

---

## 2. O que o novo feedback acrescenta

O feedback 2 traz seis temas. Para cada um, o que é novo em relação ao que já sabíamos:

| # | Tema do feedback 2 | O que acrescenta de fato |
|---|---|---|
| 1 | **Receita mais granular** (operadora → plano → contrato → beneficiário) | `[F2]` Novo. O MVP e a v1.1 só têm receita por **competência × plano**. Ninguém antes pediu receita por contrato *para análise* (o F1 pediu por contrato só como insumo do motor de reajuste). Receita por beneficiário é tema 100% novo. |
| 2 | **Relação receita × despesa no beneficiário** (resultado / saldo assistencial) | `[F2]` Novo. O F1 parou na despesa líquida. O F2 quer confrontar essa despesa com uma receita atribuída e derivar um indicador de resultado por beneficiário/contrato. |
| 3 | **Beneficiário como dimensão da explicação** (não só folha do drill) | `[F2]` Reforça e amplia o F1. O F1 entregou coortes de beneficiários *dentro* do drill de um fator. O F2 quer o beneficiário aparecendo já no primeiro nível: "58% do aumento está em 12 beneficiários". |
| 4 | **Contrato como unidade de análise** (carteira → contrato → sinistralidade → concentração → beneficiários → reajuste) | `[F2]` Reforça o F1 e sobe a aposta: o F1 introduziu `contrato` como *dimensão*; o F2 pergunta se contrato merece uma **área/módulo** próprio. |
| 5 | **Reajuste** | `[F1 + F2]` Nada de novo no conteúdo — o F1 já detalhou. O novo é a **segunda menção independente**, o que sobe a prioridade do *discovery* (não da implementação). |
| 6 | **Previsibilidade / projeção** | `[F2]` Novo. Nenhuma capacidade preditiva ou de projeção existe hoje. O gestor quer antecipar deterioração, não só explicar o passado. |

O feedback 2 **não pede**: novas telas de BI, novos gráficos, drill-downs adicionais nas
9 dimensões já cobertas, integrações, nem qualquer mudança na mecânica de bridge/Bennet.

---

## 3. Convergência entre os dois feedbacks

Esta é a seção mais importante. Os feedbacks não são listas paralelas — eles descrevem a
mesma jornada por ângulos diferentes.

### 3.1 Onde convergem

| Ponto de convergência | Feedback 1 (consultor) | Feedback 2 (gestor) | Leitura combinada |
|---|---|---|---|
| **Profundidade da explicação** | "Cardiologia caiu" não basta — quero saber *por que* (parou de consultar, saiu da carteira, evento não repetiu…), distinguindo fato/hipótese | "Quem está provocando esse comportamento e qual a relação financeira?" | A explicação completa tem **duas metades**: causa assistencial (F1) + estrutura financeira/contratual (F2). O W2Health tem a primeira (coortes), falta acoplar a segunda. `[INFERÊNCIA]` |
| **Beneficiário como driver** | Coortes de beneficiários explicam a variação de um fator | Beneficiário é dimensão de concentração, recorrência, novos casos de alto custo, receita associada | Mesma direção. O F2 quer isso **mais cedo na jornada** e **com receita ao lado**. `[F1 + F2]` |
| **Composição financeira bruta → líquida** | Despesa em camadas: bruta − glosas − coparticipação = líquida, com impacto na sinistralidade | Beneficiário: despesa bruta → glosa → coparticipação → despesa líquida → resultado | Idêntico. O F1 foi entregue **no nível da operadora** (v1.1 Etapa B). O F2 pede o **mesmo cálculo nos níveis contrato e beneficiário** (a "Fase B" que ficou no roadmap). `[F1 + F2]` |
| **Contrato como eixo** | `contrato` como dimensão + `receitas_contrato` como insumo do reajuste | Contrato como unidade de análise, possivelmente um módulo | Convergência forte. Decisão em aberto: dimensão vs. módulo (seção 9). `[F1 + F2]` |
| **Reajuste** | Módulo de simulação parametrizável, ligado à sinistralidade por contrato | Reajuste no fim da jornada do contrato | Dois profissionais, mesma lacuna. **Sobe a prioridade do discovery**, não autoriza construir. `[F1 + F2]` — `[EXIGE VALIDAÇÃO]` da regra de negócio |
| **Configuração de alertas** | Tela de regras: "beneficiário ≥ 50% do impacto → alerta" | "Beneficiários de alto impacto", "novos casos de alto custo" (alvos naturais de alerta) | O F2 não cita alertas, mas descreve exatamente os gatilhos que o motor de alertas (v1.1 Etapa C) já suporta. Falta indicador de *resultado assistencial* e de *concentração da variação* no catálogo. `[F1]` explícito, `[F2]` implícito |

### 3.2 A jornada unificada proposta pelo gestor — análise técnica

O gestor desenhou:

```
OPERADORA → SINISTRALIDADE → RECEITA × DESPESA → COMPOSIÇÃO FINANCEIRA → CONTRATO
  → DRIVER → ESPECIALIDADE → PROCEDIMENTO → PRESTADOR → BENEFICIÁRIO
  → JORNADA / EVENTOS → CAUSA OBSERVADA → INSIGHT / ALERTA → AÇÃO / DECISÃO
```

Mapeamento contra a arquitetura atual:

| Nó da jornada | Estado no W2Health | Observação |
|---|---|---|
| OPERADORA → SINISTRALIDADE | ✅ `agg_sinistralidade_competencia`, `sinistralidade.executivo/serie` | Completo |
| RECEITA × DESPESA | 🔷 Só no nível operadora (`decomposicao_sinistralidade`: efeito-despesa vs efeito-receita) | Não existe por contrato nem por beneficiário |
| COMPOSIÇÃO FINANCEIRA | 🔷 Só no nível operadora (`sinistralidade.composicao`, 4 efeitos) | "Fase B" (propagar às dimensões) não feita |
| CONTRATO | 🔷 Dimensão de **despesa** (`agg_competencia_dimensao`, `dimensao='contrato'`); sem receita própria | Não é uma "unidade" com visão own |
| DRIVER → ESPECIALIDADE → PROCEDIMENTO → PRESTADOR | ✅ `decomposition.explicar/drill`, `procedimentos`, `providers` | Completo |
| BENEFICIÁRIO | ✅ `cohorts` (coortes), `agg_beneficiario_competencia`, tela de detalhe | Aparece no drill, não no topo |
| JORNADA / EVENTOS | 🔷 Timeline simplificada (Consulta→Exame→…→Retorno) na tela do beneficiário | Não há encadeamento de episódio (sequência causal de eventos) |
| CAUSA OBSERVADA | ✅ `cohorts` com `FATO / HIPOTESE / A_INVESTIGAR` | Exatamente o que o F1 pediu |
| INSIGHT / ALERTA | ✅ `insights.py` (10 regras) + `alerts.py` (regras configuráveis) | Falta indicador de resultado assistencial |
| AÇÃO / DECISÃO | ❌ Não modelado | Nenhum registro de decisão/ação do gestor — ver seção 16 |

**Ressalva técnica importante `[INFERÊNCIA]`:** a jornada não é uma árvore linear. CONTRATO
e (ESPECIALIDADE → PROCEDIMENTO → PRESTADOR) são **eixos paralelos de decomposição**, não
níveis sequenciais — hoje o motor decompõe a variação da despesa por *uma* dimensão por
vez. "Contrato → depois driver" na verdade é: *filtrar* a análise por um contrato e então
rodar a decomposição de 9 dimensões dentro dele. Isso é viável (o filtro de escopo já
existe em `regras_alerta.escopo` e em `_filtro_dimensao`), mas é uma **composição de
recortes**, não um novo nível de árvore. Vender como "árvore de 13 níveis" seria impreciso.

---

## 4. O que já está coberto pelo W2Health

Inventário do que a v1.1 já entrega e que responde — total ou parcialmente — ao feedback 2.

### 4.1 Cobertura total

| Necessidade do F2 | Onde já está |
|---|---|
| Concentração de despesa em poucos beneficiários | `formulas.concentracao` + `gini` + Pareto; `agg_beneficiario_competencia`; insight `concentracao_beneficiarios` |
| Concentração da **variação** da despesa por beneficiário | `cohorts.analisar_causas` (participação de cada coorte na variação); indicador de alerta `beneficiario / participacao_variacao` |
| Beneficiários de alto custo | `beneficiarios_top`, tela `/beneficiarios` ordenada por custo, indicador `custo_mensal` |
| "Quem parou de usar / saiu da carteira / é novo" | `cohorts` — coortes `novos_carteira`, `novos_categoria`, `recorrentes`, `saida_carteira`, `permaneceram_sem_evento`, com selo FATO/HIPÓTESE |
| Despesa por contrato | Dimensão `contrato` em `agg_competencia_dimensao` (desde v1.1); `explicar/drill/causas` funcionam com `dimensao=contrato` |
| Vidas por contrato | `analytics_repo.contratos_vidas_mes` |
| Composição bruta → glosa → coparticipação → líquida | `sinistralidade.composicao` + `formulas.decomposicao_financeira` (**nível operadora**) |
| Distinguir efeito frequência de efeito custo médio | `formulas.bennet_bridge` + `bridge_composto` |
| Alertas configuráveis por beneficiário/contrato | `alerts.py` + `regras_alerta` + catálogo `indicadores.py` |
| Timeline assistencial do beneficiário | Tela `/beneficiarios/[id]` (Consulta → Exame → Diagnóstico → Procedimento → Internação → Retorno) |

### 4.2 Cobertura parcial (o gap é de nível/escopo, não de conceito)

| Necessidade do F2 | O que existe | O que falta |
|---|---|---|
| Composição financeira **por contrato / por beneficiário** | Cálculo pronto no nível operadora; `valor_glosado` e `valor_coparticipacao` existem **por evento** | Propagar às tabelas `agg_*` (hoje todas usam `SUM(valor_pago)` = bruta − glosa, sem coparticipação e sem bruta separada) |
| Beneficiário como dimensão **no topo** da explicação | `cohorts` roda no drill de um fator | Um "onde investigar primeiro: beneficiários" no primeiro nível de `explicar`, antes de escolher dimensão |
| Contrato como **unidade** | Dimensão de despesa | Visão consolidada do contrato (vidas + receita + despesa bruta/líquida + concentração + top beneficiários + série) |
| Recorrência / jornada de um beneficiário | Timeline visual | Métrica de recorrência, detecção de sequência de episódio, "evento não recorrente" como classificação |

---

## 5. Novas lacunas identificadas

Ordenadas por quão estrutural é a lacuna.

| # | Lacuna | Natureza | Selo |
|---|---|---|---|
| L1 | **Não existe receita abaixo do plano.** `receitas` é competência × plano. Sem receita por contrato, "sinistralidade por contrato" é impossível de calcular corretamente. | Dado ausente | `[F2]` |
| L2 | **Não existe receita por beneficiário nem metodologia de atribuição.** Nenhum rateio, prêmio per capita ou mensalidade individual no modelo. | Dado ausente + decisão de método | `[F2]` |
| L3 | **Glosa e coparticipação não são propagadas às dimensões.** Todas as `agg_*` (exceto a de competência) usam `SUM(valor_pago)`. Não dá para mostrar despesa líquida por contrato/prestador/beneficiário sem recomputar. | Engenharia sobre dado existente | `[F1 + F2]` |
| L4 | **`agg_beneficiario_competencia` só tem `despesa` e `eventos`.** Sem bruta/glosa/coparticipação, sem receita atribuída, sem flag de alto custo/recorrência. | Modelo analítico incompleto | `[F2]` |
| L5 | **Contrato não tem meta, data-base, índice de referência nem histórico de reajuste.** `contratos` só tem `id_plano`, `nome`, `tipo`. | Dado ausente (bloqueia reajuste) | `[F1 + F2]` |
| L6 | **Nenhuma capacidade de projeção.** O motor é 100% retrospectivo. Sem série projetada, sem intervalo de confiança, sem tendência. | Capacidade ausente | `[F2]` |
| L7 | **A explicação escolhe uma dimensão por vez.** Não há "dentro do contrato X, decomponha por especialidade". | Composição de recortes | `[F2]` (implícito na jornada unificada) |
| L8 | **Sem nomenclatura validada para indicadores de resultado no nível micro.** "Resultado assistencial", "relação despesa/receita" são nomes que propomos, não termos confirmados. | Risco de comunicação | `[F2]` — `[EXIGE VALIDAÇÃO]` |
| L9 | **`faixa_etaria` é fixada no seed, não recalculada por competência.** Rateio de receita por faixa e qualquer leitura de VCMH por faixa herdariam esse erro. | Aproximação documentada | `[INFERÊNCIA]` |
| L10 | **Sem registro de decisão/ação.** O último nó da jornada do gestor ("ação/decisão") não tem persistência — o produto explica, mas não acompanha o que foi feito. | Capacidade ausente | `[HIPÓTESE]` |
| L11 | **Motivo de saída do beneficiário não é capturado.** Só `data_saida` e `status`. Não dá para distinguir cancelamento, óbito, demissão, portabilidade — o que muda a leitura de "a despesa não se repetiu". | Dado ausente | `[INFERÊNCIA]` |

---

## 6. Receita como dimensão analítica

### 6.1 O que o gestor pediu

Entender receita nos níveis **operadora → plano → contrato → beneficiário** e correlacionar
com despesa. Exemplo conceitual dado: `BEN-000123` — receita atribuída R$ 7.200, despesa
líquida R$ 84.300, resultado −R$ 77.100.

### 6.2 O que existe hoje

- **Operadora:** `agg_sinistralidade_competencia.receita` (Σ das contraprestações do mês). ✅
- **Plano:** `receitas` (competência × plano); `analytics_repo.planos_sinistralidade_mes`
  já entrega sinistralidade por plano. ✅
- **Contrato:** ❌ não existe. **Detalhe relevante `[INFERÊNCIA]`:** na massa sintética
  atual há **1 contrato por plano** (12 planos, 12 contratos, mapeamento 1:1 em
  `catalogs.py`). Por acidente do gerador, `planos_sinistralidade_mes` *hoje* equivale a
  "sinistralidade por contrato". **Isso não se sustenta em um cliente real**, onde um
  plano tem dezenas ou centenas de contratos. Não devemos construir em cima dessa
  coincidência.
- **Beneficiário:** ❌ não existe, e provavelmente **não existe como dado direto** em
  operadora nenhuma (ver 6.4).

### 6.3 Receita por contrato — é derivável?

Não da forma como os dados estão. É **um dado novo que a operadora tem**, mas em outro
sistema (cadastro/faturamento), não no assistencial/TISS. Caminhos:

| Método | Quando se aplica | Precisão |
|---|---|---|
| **Contraprestação por contrato** (a operadora fatura o contrato) | Coletivo empresarial e por adesão — a fatura é do contrato | Alta — é o valor real |
| **Soma das mensalidades individuais** do contrato | Quando o faturamento é por vida (PF, alguns PME) | Alta |
| **Rateio da receita do plano por vidas do contrato** | Fallback quando só há receita por plano | Baixa — assume ticket homogêneo, ignora faixa etária e agravo |

**Recomendação `[HIPÓTESE]`:** modelar `receitas_contrato` (competência × contrato:
vidas, contraprestação, reajuste_aplicado_no_periodo) como **tabela de entrada**, populada
pelo cliente ou pelo gerador sintético — não como derivação. O rateio fica como *modo
degradado* explícito, sempre rotulado "receita estimada por rateio".

### 6.4 Receita por beneficiário — não assumir que existe

`[EXIGE VALIDAÇÃO]` Em regra, operadora **não tem "receita do beneficiário"** como
grandeza contábil. O que existe:

- **Mensalidade / contraprestação individual** (faturamento por vida): existe em planos
  individuais e em coletivos com faturamento per capita. Tem componentes: valor base por
  faixa etária (10 faixas RN 63/ANS), agravo (pré-existência), desconto/subsídio do
  empregador, coparticipação faturada à parte.
- **Titular × dependente:** a mensalidade do dependente costuma ser distinta; atribuir a
  "receita do núcleo familiar" a um beneficiário exige regra.
- **Coletivo empresarial com preço médio:** a empresa paga um valor global; **não há**
  mensalidade por vida — só rateio (por vida, por faixa, ou por sinistralidade).
- **Pool de risco (PME < 30 vidas, RN 309):** o preço é do pool, não do contrato — receita
  por contrato já é uma abstração.

**Metodologias de atribuição possíveis**, em ordem de fidelidade:

1. Mensalidade individual faturada (quando existe) — fiel.
2. Prêmio per capita = contraprestação do contrato / vidas — simples, ignora faixa.
3. Rateio por faixa etária = contraprestação do contrato distribuída pelos fatores de
   faixa da tabela do plano — melhor, exige a tabela de fatores e faixa por competência (L9).
4. Rateio por participação na despesa — **não recomendado**: circular (usa despesa para
   atribuir receita), destrói o sentido de "resultado".

**Decisão de produto necessária (seção 22):** qual é o método *default*, e como deixar
explícito na UI que é uma **atribuição**, não uma receita real.

---

## 7. Relação receita × despesa

### 7.1 Indicadores candidatos

Assumindo que exista uma **receita atribuída** `Ra` (por contrato ou por beneficiário) e a
**despesa líquida** `Dl` (bruta − glosa − coparticipação), os indicadores que fazem
sentido:

| Nome proposto (neutro) | Fórmula | Interpretação | Selo |
|---|---|---|---|
| **Resultado assistencial** | `Ra − Dl` | Saldo em R$ entre o que entrou (atribuído) e o que a operadora gastou (líquido) | `[F2]` deu o nome; `[EXIGE VALIDAÇÃO]` |
| **Relação despesa/receita** | `Dl / Ra` (×100) | Quantos % da receita atribuída foram consumidos em assistência | `[F2]` deu o nome; `[EXIGE VALIDAÇÃO]` |
| **Saldo assistencial acumulado** | `Σ(Ra − Dl)` na janela | Versão 12m / desde a adesão | `[HIPÓTESE]` |
| **Índice de utilização financeira** | `Dl / Ra`, sinônimo neutro alternativo | Mesmo que acima, se "relação despesa/receita" soar ruim em entrevista | `[HIPÓTESE]` |

### 7.2 O que NÃO fazer

`[F2]` explícito: **não chamar `Dl / Ra` de "sinistralidade individual"** sem evidência de
que o mercado usa esse termo. Sinistralidade é um conceito de **carteira/contrato** com
receita contábil real; aplicá-lo a um beneficiário com receita *rateada* é uma extrapolação.
Todo indicador micro entra no produto com **rótulo provisório + aviso "nomenclatura a
validar com negócio"** até uma entrevista confirmar.

### 7.3 Onde isso encaixa no motor

- `formulas.py` ganharia primitivas puras `resultado_assistencial(ra, dl)` e
  `relacao_despesa_receita(ra, dl)` — testáveis, sem I/O, no padrão atual.
- Só faz sentido depois de L3 (glosa/coparticipação por dimensão) e L2 (receita atribuída).
- **Risco de interpretação alto:** um "resultado −R$ 77 mil" por beneficiário lido fora de
  contexto vira "esse beneficiário dá prejuízo" — ignorando que seguro é mutualização. A
  UI precisa sempre mostrar o indicador **agregado ao contrato/carteira**, com o
  beneficiário como *contribuição*, nunca como veredito isolado. `[INFERÊNCIA]`

---

## 8. Beneficiário como unidade de inteligência

### 8.1 O que muda em relação à v1.1

Hoje o beneficiário é: (a) uma lista ordenada por custo, (b) uma folha do drill via
`cohorts`, (c) uma tela de detalhe com timeline. O F2 quer que ele seja **um ângulo de
entrada da explicação**.

### 8.2 Capacidades pedidas e viabilidade

| Capacidade | Viável com dados atuais? | Como |
|---|---|---|
| Concentração de despesa | ✅ já existe | `concentracao` sobre `agg_beneficiario_competencia` |
| Concentração da **variação** | ✅ já existe (no drill) | `cohorts`; falta expor no topo |
| Beneficiários de alto impacto | ✅ | ordenar coortes por `participacao_variacao` |
| Recorrência | 🔷 derivável | contar meses com evento na série `beneficiario_serie` — precisa de uma métrica nova |
| Novos casos de alto custo | 🔷 derivável | beneficiário sem despesa relevante nos meses anteriores e acima de um limiar agora — regra nova |
| Eventos não recorrentes | 🔷 derivável | `procedimentos.perfil_utilizacao='pontual'` + ausência de repetição na série |
| Mudança de comportamento | 🔷 parcial | `cohorts` detecta troca de prestador; "mudança de comportamento" mais ampla é vaga — `[EXIGE VALIDAÇÃO]` do que o gestor quer dizer |
| Receita associada | ❌ | depende de L2 |
| Despesa associada (líquida) | 🔷 | `valor_pago` sim; líquida depende de L3 |

### 8.3 Conexão com coortes (F1)

A coorte já classifica **por que** a despesa de um fator mudou em termos de população. O
F2 pede o **espelho**: começar pelo beneficiário e perguntar em quais fatores ele pesa.
São a mesma tabela de fatos lida por chaves diferentes — `eventos_assistenciais` filtrado
por `id_beneficiario` já responde. É engenharia de apresentação, não de modelo. `[INFERÊNCIA]`

### 8.4 Proposta conceitual (não implementar)

Um bloco **"Onde investigar primeiro — beneficiários"** no resultado de `explicar()` (antes
do drill por dimensão), mostrando: top-N por contribuição à variação, com selo
FATO/HIPÓTESE herdado das coortes, receita atribuída (se L2 existir) e link para o detalhe.
`[HIPÓTESE]`

---

## 9. Contrato como unidade de inteligência

### 9.1 A pergunta do gestor

Contrato deveria ser: (a) só uma dimensão do motor, (b) uma tela, (c) um módulo, (d) uma
capacidade futura maior?

### 9.2 Análise

| Opção | Prós | Contras | Leitura |
|---|---|---|---|
| **(a) Só dimensão** (estado atual) | Zero custo; já funciona em `explicar/drill/causas` | Não responde "me mostre o contrato X inteiro"; sem receita própria | Insuficiente para o que o F2 descreve |
| **(b) Uma tela** `/contratos` + `/contratos/[id]` | Consolida vidas + despesa bruta/líquida + concentração + top beneficiários + série em um lugar; reaproveita `explicar` com escopo | Só vira "Contract Intelligence" de verdade com receita por contrato (L1) | **Caminho recomendado como próximo passo** `[HIPÓTESE]` |
| **(c) Módulo** (reajuste, simulação, metas, histórico) | É a visão completa que os dois feedbacks sugerem | Depende de L1 + L5 + discovery de reajuste; escopo grande | Roadmap, depois do discovery de reajuste |
| **(d) Capacidade futura** | — | — | É a soma de (b) + (c) ao longo do tempo |

### 9.3 Jornada do contrato (conceitual, não implementar)

```
Carteira → Contrato → Vidas → Despesa (bruta/líquida) → [Receita] → [Sinistralidade]
  → Concentração (Gini/Pareto sobre beneficiários do contrato)
  → Beneficiários de maior impacto (coortes com escopo=contrato)
  → Drivers dentro do contrato (explicar com escopo=contrato)
  → Eventos / Jornada
  → [Reajuste / Simulação]   ← trilha separada, ver seção 10
```

Os nós entre colchetes dependem de dados/decisões ainda não tomados. Os demais são
**recorte** do que já existe.

### 9.4 Recomendação

Tratar contrato como **tela** (opção b) numa v1.2, **sem** receita própria e **sem**
reajuste — exatamente o escopo que a v1.1 já sustenta (dimensão + `contratos_vidas_mes` +
coortes com `dimensao=contrato`). Evoluir para módulo só quando L1 e o discovery de
reajuste estiverem resolvidos. `[INFERÊNCIA]`

---

## 10. Reajuste — hipóteses e perguntas em aberto

**Não implementar.** O F1 já produziu uma proposta técnica detalhada
([EVOLUCAO_FEEDBACK_ESPECIALISTA.md](EVOLUCAO_FEEDBACK_ESPECIALISTA.md) §5). O F2 confirma
o interesse. Falta a **regra de negócio real** — que varia por operadora e por tipo de
contrato, e é regulada pela ANS.

### 10.1 O que já sabemos que é preciso (do F1)

`receitas_contrato`, `contrato_parametros_reajuste` (data-base, índice, meta, metodologia),
`contrato_reajuste_historico`, motor `reajuste.py` com estratégias plugáveis, endpoint de
simulação. Complexidade avaliada como **Alta**.

### 10.2 Roteiro de discovery específico para REAJUSTE

Perguntas a responder **antes de qualquer código**, agrupadas:

**Base de cálculo**
- Qual período de sinistralidade é usado? (12 meses móveis? ano-safra? últimos N meses?)
- A base é sinistralidade **bruta** ou **líquida** (pós-glosa/coparticipação)?
- Entram IBNR / provisões / despesas administrativas no cálculo, ou só sinistro puro?
- Como se trata mês incompleto / eventos em processamento?

**Meta e recomposição**
- Existe **meta de sinistralidade por contrato**? Quem define — atuária, comercial, negociação?
- A fórmula de recomposição é `(apurada / meta) − 1`? Tem teto? Piso? Banda de tolerância?
- Recompõe 100% do desvio de uma vez ou dilui em N reajustes?

**Índices**
- Usa **VCMH** (Variação de Custo Médico-Hospitalar)? De qual fonte (IESS, própria, consultoria)?
- Combina índice financeiro (IPCA/IGPM) + índice técnico (sinistralidade)? Com que pesos?
- Para PF/individual: o índice é o **teto ANS** (divulgado anualmente)? O produto só monitora?

**Segmentação regulatória**
- PME < 30 vidas: entra em **pool de risco** (RN 309)? O reajuste é do pool, não do contrato?
- Coletivo ≥ 30 vidas: livre negociação — que dados suportam a mesa de negociação?
- Individual/familiar: teto ANS — o produto ajuda a **contestar** ou só a **projetar**?

**Vidas e mix**
- Como a **quantidade de vidas** afeta o reajuste? (credibilidade atuarial: contrato
  pequeno → mais peso no pool/mercado, menos na experiência própria)
- Mudança de **mix de faixa etária** entra separada do reajuste anual (reajuste por
  mudança de faixa, RN 63) ou é tudo junto?

**Processo**
- Existe **histórico de reajustes** aplicados? Em que granularidade?
- Como a **data-base** interfere (contrato reajusta em aniversário, não em janeiro)?
- Há **negociação manual** que sobrepõe o cálculo? O produto registra o "sugerido" vs. o "aplicado"?
- Que informações **regulatórias** precisam constar (protocolo ANS, nota técnica, RN aplicável)?

### 10.3 Entregável do discovery de reajuste

Um documento `docs/DISCOVERY_REAJUSTE.md` (futuro) com: a fórmula real de 1–2 operadoras,
o mapa de variação por tipo de contrato, e a decisão de **quais metodologias o motor
precisa suportar** — antes de reabrir a §5 do doc do F1.

---

## 11. Previsibilidade — o que poderíamos prever

**Não implementar ML.** Primeiro decidir **o que** vale prever e **com qual método**.

### 11.1 Três conceitos que não podem se misturar

| Conceito | O que é | Postura do W2Health |
|---|---|---|
| **Projeção estatística** | Extrapolar uma série histórica (média móvel + fator sazonal + intervalo de confiança). Sem "features", sem treino. | **Candidata** — o motor de sazonalidade já tem metade disso |
| **Modelo preditivo** | Aprender de features (idade, CID, histórico, prestador…) para prever um alvo. Exige treino, validação, monitoramento de drift. | **Roadmap distante** — só com dados reais e governança |
| **Previsão clínica** | Prever desfecho de saúde de um indivíduo (agravo, internação, óbito). | **Fora de escopo, permanente.** O produto não faz diagnóstico nem decisão clínica automatizada |

### 11.2 O que vale prever — avaliação

| Alvo | Valor p/ negócio | Viabilidade c/ dados atuais | Risco de interpretação | Complexidade | Veredito |
|---|---|---|---|---|---|
| **Receita futura** (operadora/contrato) | Médio | **Alta** — contraprestação é quase determinística (vidas × ticket × reajuste conhecido) | Baixo | Baixa | Projeção estatística — bom candidato |
| **Despesa líquida futura** | Alto | Média — série de 24m, sazonalidade modelada; ruído ±10% mês a mês | Médio | Média | Projeção com IC largo, sempre com banda |
| **Sinistralidade futura** (operadora) | Alto | Média — razão de duas projeções, erro compõe | **Alto** — gestor tende a ler projeção como compromisso | Média | Projeção estatística, rotulada "cenário, não meta" |
| **Sinistralidade futura por contrato** | **Alto** | Baixa hoje (sem receita por contrato; contratos pequenos = série instável) | Alto | Média-Alta | Depende de L1; validar antes |
| **Frequência / custo médio futuros** | Médio | Média | Médio | Média | Só se a projeção de despesa pedir decompor |
| **Deterioração da sinistralidade do contrato** (sinal, não número) | **Alto** | Média — combina tendência + concentração + novos casos de alto custo | Médio (é um alerta, não uma previsão pontual) | Média | **Melhor candidato** — vira regra/alerta, não modelo |
| **Beneficiários com potencial de alto custo** | Alto (se confiável) | **Baixa** — sem CID longitudinal estruturado, sem cronicidade, sem medicação | **Muito alto** — parece score de risco individual; risco ético/regulatório | Alta | **Não priorizar** |
| **Beneficiários já de alto custo recorrente** (fato, não previsão) | Alto | Alta — é leitura da série | Baixo | Baixa | Já quase pronto (seção 8.2) — não é "previsão" |

### 11.3 Recomendação

Se previsibilidade entrar, começar por **"sinais de deterioração do contrato"** (uma
regra sobre tendência + concentração + novos casos, na linha do motor de alertas) e por
**projeção estatística de despesa/receita com intervalo de confiança visível**. Nada de
modelo treinado, nada no nível do indivíduo. Validar apetite e leitura em entrevista antes.
`[HIPÓTESE]` + `[EXIGE VALIDAÇÃO]`

---

## 12. Impacto no modelo de dados

Classificação pedida pelo enunciado: **já existe / derivável / precisa adicionar / exige
nova fonte em cliente real.**

### 12.1 Já existe (nenhuma mudança)

- `beneficiarios.data_adesao`, `data_saida`, `status` → entrada/saída de carteira.
- `beneficiarios.id_contrato`, `id_plano` → recorte por contrato/plano.
- `eventos_assistenciais.valor_apresentado / valor_glosado / valor_pago / valor_coparticipacao`
  → composição financeira **por evento** (base para agregar em qualquer grão).
- `procedimentos.perfil_utilizacao` → apoio à classificação pontual/recorrente.
- `agg_competencia_dimensao` com `dimensao='contrato'` → despesa (valor_pago) por contrato.
- `receitas` (competência × plano) + `planos.percentual_coparticipacao`.
- `agg_beneficiario_competencia` (despesa, eventos por mês).
- `cenarios_gabarito`, `regras_alerta`, catálogo `indicadores.py`.

### 12.2 Derivável (engenharia, sem novo dado de entrada)

| Derivação | A partir de | Custo |
|---|---|---|
| Despesa **líquida** por contrato / prestador / beneficiário | `eventos_assistenciais` (recomputar `agg_*` com bruta/glosa/coparticipação) | Reescrever `aggregate.py` + colunas nas `agg_*` |
| Concentração / Gini / Pareto **dentro de um contrato** | `agg_beneficiario_competencia` + `beneficiarios.id_contrato` | Baixo — filtro |
| Coortes **com escopo de contrato** | `cohorts` já aceita `dimensao='contrato'`; para "contrato + especialidade" precisa de filtro composto | Baixo-Médio |
| Recorrência de um beneficiário | `beneficiario_serie` (contar meses com evento) | Baixo — métrica nova |
| "Novo caso de alto custo" | série do beneficiário + limiar | Baixo — regra |
| Receita por contrato **por rateio** (modo degradado) | `receitas` (plano) ÷ vidas do contrato | Baixo — mas impreciso, rotular |

### 12.3 Precisa adicionar (modelo/analítico — dado plausível de já existir no cliente)

| Adição | Para quê | Selo |
|---|---|---|
| Colunas `despesa_bruta / glosas / coparticipacao / despesa_liquida` em `agg_competencia_dimensao`, `agg_prestador_competencia`, `agg_beneficiario_competencia` | Composição financeira em todos os níveis (Fase B do F1) | `[F1 + F2]` |
| Tabela `receitas_contrato` (competência × contrato: vidas, contraprestação, reajuste_no_periodo) | Sinistralidade e resultado por contrato | `[F2]` |
| Tabela/coluna de **receita atribuída por beneficiário** + `metodologia_atribuicao` | Resultado assistencial por beneficiário | `[F2]` — `[EXIGE VALIDAÇÃO]` do método |
| `agg_contrato_competencia` (vidas, receita, despesa bruta/líquida, sinistralidade, gini, n_beneficiarios_alto_custo) | Tela/visão de contrato performática | `[HIPÓTESE]` |
| `contratos.meta_sinistralidade`, `data_base`, `indice_referencia` + `contrato_reajuste_historico` | Reajuste (só após discovery §10) | `[F1 + F2]` — bloqueado |
| Métricas de beneficiário: `recorrencia_meses`, `flag_alto_custo`, `flag_novo_caso` | Beneficiário como dimensão de entrada | `[F2]` |
| `faixa_etaria` recalculada por competência (ou fator de faixa por competência) | Rateio de receita por faixa; leitura de VCMH | `[INFERÊNCIA]` (L9) |
| `beneficiarios.motivo_saida` | Ler corretamente "a despesa não se repetiu" | `[INFERÊNCIA]` (L11) |

### 12.4 Exige nova fonte de dados em um cliente real

Estes **não vêm do sistema assistencial / TISS** — vêm de cadastro, faturamento, atuária
ou fontes externas, e a integração é um projeto próprio:

| Dado | Fonte típica no cliente | Por que não dá para inferir |
|---|---|---|
| Contraprestação / prêmio **por contrato** | Sistema de faturamento / ERP financeiro | O assistencial não conhece o valor faturado |
| **Mensalidade individual** (titular/dependente, agravo, subsídio) | Cadastro comercial / faturamento | Idem; e coletivo empresarial pode nem ter |
| Tabela de **fatores de faixa etária** do plano | Nota técnica atuarial / cadastro de produto | Regulada, específica por produto |
| **Reajustes históricos** aplicados + data-base + RN aplicável | Área de contratos / regulatório | Decisão de negócio, não registrada em evento |
| **VCMH** / índices de mercado | IESS, ANS, consultoria atuarial | Fonte externa |
| **Meta de sinistralidade** por contrato | Atuária / comercial | Definição interna |
| **Desfecho clínico / conclusão de tratamento** | Gestão de casos, autorização, laudo, protocolo | **Não inferível** de ausência de evento — a coorte só pode marcar HIPÓTESE, nunca fato |
| **Motivo de saída** (óbito, demissão, portabilidade, inadimplência) | Cadastro / movimentação | `data_saida` não carrega o motivo |
| Cronicidade / linha de cuidado / medicação contínua | Programa de gestão de crônicos, farmácia | Fora do modelo de eventos atual |

**Limitações que queremos explícitas** (conforme pedido no enunciado):

- `data_saida` do beneficiário: **já existe** — dá para saber *que* saiu, não *por quê*.
- Receita por beneficiário: **não existe diretamente** — sempre será atribuição/rateio,
  com metodologia declarada.
- Conclusão de tratamento: **não pode ser inferida** dos dados — permanece HIPÓTESE
  rotulada, nunca FATO.
- Sinistralidade por contrato: **não é derivável hoje** — depende de receita por contrato
  como dado de entrada.

---

## 13. Dados necessários em uma operadora real

Se o W2Health for implantado em um cliente, o "contrato de dados" mínimo por capacidade:

| Capacidade | Dados mínimos que o cliente precisa fornecer |
|---|---|
| Sinistralidade da operadora (MVP) | Eventos assistenciais (valor apresentado, glosado, pago, coparticipação); contraprestação total por mês |
| Composição financeira por dimensão | Glosa e coparticipação **por evento** (não só total) |
| Sinistralidade por plano | Contraprestação por plano/mês; vínculo beneficiário → plano |
| **Sinistralidade por contrato** | Contraprestação **por contrato**/mês; vínculo beneficiário → contrato; vidas por contrato/mês |
| **Resultado por beneficiário** | Mensalidade individual **ou** regra de rateio acordada + tabela de faixas; data de nascimento confiável |
| Coortes / "quem saiu" | `data_adesao`, `data_saida`, `status` e — desejável — `motivo_saida` |
| Jornada assistencial | Eventos com data, tipo, procedimento, diagnóstico (CID), prestador — idealmente com autorização/senha para encadear episódio |
| **Reajuste** | Meta por contrato; data-base; índice de referência; histórico de reajustes; RN aplicável; (externo) VCMH |
| Previsibilidade estatística | ≥ 24 meses de série contínua e consistente; sem rupturas de escopo de carteira não sinalizadas |
| Alertas | Nada além do acima — o motor calcula sobre o que já entrou |

**Observação de integração `[INFERÊNCIA]`:** os dados assistenciais e os financeiros/
cadastrais quase sempre moram em sistemas diferentes (ex.: assistencial em Tasy/MV,
faturamento em outro ERP). A capacidade "receita granular" é, na prática, **um projeto de
integração de duas fontes**, não uma feature de motor.

---

## 14. Evolução da massa sintética

Objetivo: permitir **demonstrar** as capacidades discutidas, sem construir nada agora —
só desenhar o alvo.

### 14.1 Mudança estrutural necessária

1. **Quebrar o 1:1 plano↔contrato.** Passar de 12 contratos para ~40–60, com **múltiplos
   contratos por plano** e tamanhos muito díspares (de ~15 vidas a ~6.000). Isso é
   pré-requisito para qualquer cenário de contrato ser convincente.
2. **Gerar `receitas_contrato`** (competência × contrato), calibrada para uma
   sinistralidade-alvo por contrato variada (ex.: alguns a 60%, outros a 95%), com
   data-base espalhada pelo ano e um histórico de reajuste plausível.
3. **Atribuir receita por beneficiário** por rateio de faixa (exige fator de faixa por
   plano no catálogo) — marcada como estimada.
4. **Propagar bruta/glosa/coparticipação** às agregações por dimensão (para a demo de
   despesa líquida por contrato/beneficiário).

### 14.2 Cenários A–I — desenho e perguntas que cada um responde

| Cenário | O que plantar nos dados | Pergunta que permite responder | Reaproveita |
|---|---|---|---|
| **A** — poucos beneficiários deterioram um contrato | Contrato médio (~300 vidas); 4–6 beneficiários com terapias de altíssimo custo a partir do mês M; receita do contrato estável | "A piora do contrato X é estrutural ou concentrada? Em quantas vidas?" | lógica do `s4_alto_custo`, com escopo de contrato |
| **B** — receita estável, surgem casos de alto custo | Como A, mas ênfase em **novos** casos (sem despesa relevante antes de M) | "Isso é deterioração nova ou agravamento de casos antigos?" | `s4` + flag `novo_caso` |
| **C** — despesa sobe, reajuste/receita compensa parcialmente | Contrato com +25% de despesa líquida em 12m **e** reajuste de +18% na data-base → sinistralidade sobe pouco | "O reajuste passado foi suficiente? Quanto do desvio ele cobriu?" | novo — exige `receitas_contrato` + histórico |
| **D** — receita cai por saída de vidas, despesa fica | Contrato perde ~30% das vidas em 3 meses (demissões); despesa absoluta cai menos que proporcional → sinistralidade piora pelo **denominador e pelo mix** | "A piora é por gasto ou por perda de escala? Quem saiu — os saudáveis?" | `s9_receita_estagnada` + `data_saida` em lote |
| **E** — jornada assistencial identificável | 1 beneficiário com sequência encadeada: consulta cardio → exames → diagnóstico → cirurgia → internação → retornos, ao longo de 4–5 meses | "Esse custo é um episódio com início/meio/fim ou uso crônico?" | timeline existente + `cenario_tag` encadeado |
| **F** — evento de alto custo pontual que não repete | 1 procedimento `perfil_utilizacao='pontual'` de valor alto em 1 mês, sem repetição | "Esse pico volta mês que vem? (não) — a coorte marca HIPÓTESE de episódio concluído" | `s1` (catarata) + `cohorts` |
| **G** — grupo recorrente aumenta frequência | ~400 beneficiários com +2 idas/mês ao pronto-socorro a partir de M, estáveis na carteira | "É frequência ou custo? População nova ou a mesma usando mais?" | `s6_ps_recorrente` |
| **H** — contrato melhora só por aumento de receita | Despesa líquida ~constante; reajuste de +22% na data-base → sinistralidade cai visivelmente sem nenhuma ação assistencial | "A melhora é gestão de custo ou só preço? É sustentável?" | novo — exige `receitas_contrato` |
| **I** — concentração extrema em poucos beneficiários | Contrato onde 3 beneficiários = 70% da despesa (Gini > 0,8) | "Faz sentido reajustar o contrato inteiro ou é caso de gestão individual / stop-loss?" | `concentracao` + `gini` com escopo de contrato |

### 14.3 Gabarito

Cada cenário ganha linha em `cenarios_gabarito` (o padrão já usado nos 13 cenários
atuais), com `efeito_esperado` estendido para novos rótulos: `concentracao_contrato`,
`receita_contrato`, `reajuste_compensa`, `jornada_episodio`. Testes no padrão de
`test_scenarios.py` / `test_cohorts.py`.

---

## 15. Possível arquitetura funcional do produto

O enunciado sugere organizar o W2Health em capacidades nomeadas. Avaliação `[HIPÓTESE]`:

| Capacidade sugerida | O que agrupa | Já existe? | Vale como rótulo de roadmap? |
|---|---|---|---|
| **Executive Intelligence** | Visão executiva da carteira (KPIs, evolução, fatores de atenção) | ✅ tela `/` | Sim — é a Home atual |
| **Loss Ratio Intelligence** | Explicação da sinistralidade (decomposição, bridge, coortes, composição financeira) | ✅ tela `/sinistralidade` + `cohorts` + `composicao` | Sim — é o coração do produto |
| **Contract Intelligence** | Contrato: vidas, receita, despesa, concentração, (futuro) reajuste | 🔷 só dimensão | Sim — é o próximo bloco a construir |
| **Beneficiary Intelligence** | Impacto financeiro + comportamento + jornada + (futuro) resultado assistencial | 🔷 lista + detalhe + coortes | Sim — mas cuidar do risco de "score individual" |
| **Provider Intelligence** | Prestadores: frequência, custo, anomalia vs. pares | ✅ tela `/prestadores` | Sim — já maduro |
| **Alerts** | Monitoramento configurável | ✅ `/configuracao/insights` + aba em `/insights` | Sim — já existe |

### 15.1 Recomendação

**Adotar esses nomes como linguagem interna de roadmap e como agrupamento da navegação —
não como produtos separados, não como seis áreas novas de código.** O backend continua um
monólito modular; `app/analytics/` já é organizado por capacidade (`decomposition`,
`cohorts`, `providers`, `alerts`…). O ganho é de **comunicação e priorização**: fica claro
que "Contract Intelligence" é onde está o próximo investimento e que "previsão de
beneficiário de alto custo" **não pertence** a "Beneficiary Intelligence" no curto prazo.

### 15.2 Organização alternativa (se a modular não convencer)

Organizar por **pergunta de decisão** em vez de por entidade:

- "Minha sinistralidade mudou — por quê?" (existe)
- "Este contrato está saudável? Devo agir nele?" (a construir)
- "Onde está concentrado o risco — e é episódio ou crônico?" (parcial)
- "O que vai acontecer se eu não fizer nada?" (previsibilidade — a validar)
- "O que me avisa antes de virar problema?" (alertas — existe)

Isso amarra melhor à tese *decision intelligence* e resiste à tentação de "uma tela por
entidade". `[INFERÊNCIA]`

---

## 16. Impacto na experiência do usuário

`[INFERÊNCIA]` em toda a seção.

### 16.1 Onde o produto ganha sem inchar

- **Concentração de beneficiários no topo da explicação** — em vez de o gestor descer 3
  níveis, o resultado de `explicar()` já diz "58% em 12 vidas". Menos cliques, mais decisão.
- **Um seletor de contrato como escopo global** (ao lado de competência/comparação) — a
  mesma tela de Sinistralidade, filtrada. Não é tela nova; é um filtro.
- **Composição bruta/líquida onde já se olha despesa** — card, não página.

### 16.2 Riscos de UX a evitar

| Risco | Mitigação |
|---|---|
| "Resultado assistencial −R$ 77 mil" por beneficiário lido como veredito | Sempre mostrar o número **agregado** (contrato/carteira) como principal e o beneficiário como *contribuição*; texto fixo "seguro é mutualização" |
| Receita atribuída confundida com receita real | Rótulo permanente "receita estimada — método: rateio por faixa"; ícone/tooltip |
| Nomenclatura não validada virar padrão de fato | Selo "termo provisório, a validar" até entrevista confirmar |
| Projeção lida como meta/compromisso | Banda de confiança sempre visível; rótulo "cenário, não previsão contratual" |
| Virar "Power BI de 50 páginas" | Regra de ouro (seção 18): toda tela/bloco novo tem que responder a uma pergunta de decisão listada, não "mostrar mais um dado" |

### 16.3 Navegação

No máximo **+1 item de menu** ("Contratos") numa v1.2. "Beneficiários" já existe.
"Configuração" já existe. Previsibilidade, se entrar, é um **bloco dentro** de Executive/
Contract, não uma seção.

---

## 17. Priorização das capacidades

Escala 1–5. **Valor p/ gestor** · **Validação pelos feedbacks** · **Dependência de novos
dados** · **Complexidade técnica** · **Risco de interpretação**. (Em dependência/
complexidade/risco, 5 = pior.)

| # | Capacidade | Valor | Valid. | Dep. dados | Complex. | Risco | Recomendação |
|---|---|:-:|:-:|:-:|:-:|:-:|---|
| C1 | Concentração de beneficiários no **topo** de `explicar()` (coortes + Pareto no 1º nível) | 4 | 5 | 1 | 2 | 2 | **FAZER AGORA** |
| C2 | Propagar bruta/glosa/coparticipação às `agg_*` → despesa **líquida** por contrato/prestador/beneficiário (Fase B do F1) | 4 | 5 | 1 | 3 | 2 | **FAZER AGORA** |
| C3 | Escopo de **contrato** na explicação (filtrar `explicar/drill/causas` por contrato) | 4 | 4 | 1 | 2 | 2 | **FAZER AGORA** |
| C4 | Tela **`/contratos`** (vidas + despesa bruta/líquida + concentração + top beneficiários + série), **sem receita própria** | 4 | 4 | 2 | 3 | 2 | **FAZER AGORA** (v1.2) |
| C5 | Métricas de beneficiário: recorrência, novo caso de alto custo, evento não recorrente | 3 | 4 | 2 | 2 | 3 | **FAZER AGORA** |
| C6 | Indicadores novos no catálogo de alertas: participação na variação (topo), concentração de contrato | 3 | 4 | 1 | 2 | 2 | **FAZER AGORA** |
| C7 | `receitas_contrato` → **sinistralidade por contrato** de verdade | 5 | 4 | 4 | 3 | 3 | **VALIDAR ANTES** (fonte existe? qual grão?) |
| C8 | **Receita atribuída por beneficiário** (rateio) + resultado assistencial | 4 | 4 | 5 | 4 | 5 | **VALIDAR ANTES** (método + nomenclatura + uso) |
| C9 | Nomenclatura dos indicadores micro (resultado assistencial / relação despesa-receita) | 3 | 4 | 1 | 1 | 4 | **VALIDAR ANTES** (1 pergunta de entrevista resolve) |
| C10 | `faixa_etaria` por competência + fatores de faixa | 2 | 2 | 3 | 3 | 2 | **ROADMAP** (pré-req de C8 por rateio de faixa) |
| C11 | Encadeamento de **jornada / episódio** (cenário E) | 3 | 3 | 2 | 3 | 3 | **ROADMAP** |
| C12 | **Projeção estatística** de despesa/receita/sinistralidade com IC | 4 | 3 | 2 | 3 | 4 | **VALIDAR ANTES** (apetite + leitura) |
| C13 | **"Sinais de deterioração de contrato"** (regra tendência + concentração + novos casos) | 4 | 3 | 2 | 3 | 3 | **VALIDAR ANTES** |
| C14 | **Módulo de reajuste / simulação** | 5 | 5 | 5 | 5 | 4 | **ROADMAP** (só após `DISCOVERY_REAJUSTE.md`) |
| C15 | Reorganização modular (Executive/Loss Ratio/Contract/Beneficiary/Provider/Alerts) como linguagem de roadmap e navegação | 2 | 3 | 1 | 1 | 1 | **FAZER AGORA** (é rótulo, não código) |
| C16 | **Modelo preditivo** de beneficiário de alto custo | 3 | 2 | 5 | 5 | 5 | **NÃO PRIORIZAR** |
| C17 | Registro de **decisão/ação** do gestor (último nó da jornada) | 3 | 2 | 2 | 3 | 2 | **NÃO PRIORIZAR** agora |
| C18 | `motivo_saida` do beneficiário | 2 | 1 | 4 | 2 | 1 | **ROADMAP** (melhora leitura de coortes) |

### 17.1 Bloco "FAZER AGORA" (proposta de v1.2)

C1 + C2 + C3 + C4 + C5 + C6 + C15. Todos: **sem novos dados de entrada**, **sem escrita
adicional** além da já existente, **sem autenticação nova**. É a "Fase B" do F1 + o
recorte de contrato do F2, entregues juntos. Mantém o produto no mesmo perfil de baixo
risco da v1.1.

### 17.2 O que fica de fora da v1.2 (deliberadamente)

Receita por contrato/beneficiário, reajuste, previsibilidade, jornada encadeada, registro
de decisão. Cada um tem uma pré-condição não resolvida (dado, método, ou discovery).

---

## 18. O que NÃO devemos construir agora

| Não construir | Por quê | Quando reconsiderar |
|---|---|---|
| Módulo de **reajuste** | Regra de negócio desconhecida; regulada; varia por operadora/contrato | Depois de `DISCOVERY_REAJUSTE.md` com fórmula real de ≥1 cliente |
| **Machine learning** de qualquer tipo | Sem dados reais, sem governança, sem necessidade validada | Só com dados reais + demanda explícita + plano de validação/drift |
| **Score de risco / previsão de alto custo por indivíduo** | Risco ético/regulatório alto; dados insuficientes; contradiz "sem decisão clínica" | Provavelmente nunca no formato individual; talvez como coorte agregada |
| "**DRE por beneficiário**" como veredito | Seguro é mutualização; número isolado engana | Nunca como veredito; só como *contribuição* dentro do contrato |
| **Sinistralidade por contrato** sobre o 1:1 sintético atual | É coincidência do gerador, não vale para cliente real | Depois de `receitas_contrato` + massa com N contratos por plano |
| Nova **nomenclatura de mercado** inventada ("sinistralidade individual") | Sem evidência de uso | Se uma entrevista confirmar o termo |
| **Telas de visualização** que não respondem a uma pergunta de decisão | Tese é *decision intelligence*, não BI | — |
| **Autenticação/multi-tenant** dentro desta rodada | Fora do escopo do discovery; já registrado como dívida | Antes de qualquer uso real com cliente |
| Materializar coortes / `agg_beneficiario_dimensao_competencia` | Multiplicaria a maior `agg_` por ~10×; drill é baixo tráfego | Só se `--beneficiarios 100000` ficar lento na prática |

---

## 19. Perguntas para próximas entrevistas

Perguntas capazes de **validar ou invalidar** funcionalidades — não perguntas de opinião.

### Sinistralidade
1. Quando a sinistralidade da carteira sobe, qual é a **primeira quebra** que você faz —
   por contrato, por especialidade, por prestador, ou por beneficiário? Em que ordem?
2. Você separa o efeito de **glosa e coparticipação** da despesa "de verdade" quando
   analisa a variação? Esse número circula na diretoria ou fica na área técnica?
3. Quando descobre que a alta está concentrada em poucos beneficiários, isso **muda a
   decisão** — ou o tratamento é o mesmo de uma alta difusa?

### Receita
4. Vocês têm a **contraprestação no nível do contrato** disponível para análise, ou ela só
   existe consolidada por plano / pela operadora? Em qual sistema?
5. Para um coletivo empresarial com preço médio, existe algum número de **receita por
   vida**, ou isso nunca é calculado? Se calculam, como (per capita, por faixa, outro)?
6. Faz sentido para você ver **"receita atribuída vs. despesa líquida" por beneficiário**,
   sabendo que a receita seria um rateio? Ou isso confunde mais do que ajuda?

### Contratos
7. Quando um contrato ultrapassa a meta de sinistralidade, qual é a **primeira análise**
   que você faz antes de discutir reajuste?
8. Existe **meta de sinistralidade formal por contrato**? Quem define e onde ela está
   registrada?
9. O que você precisa ver de um contrato **em uma tela só** para decidir se ele exige ação
   — e o que hoje você tem que buscar em três lugares?

### Beneficiários
10. Como você distingue hoje um beneficiário com **episódio de alto custo que vai acabar**
    de um com **custo crônico que veio para ficar**? Que dado te diz isso?
11. "Novo caso de alto custo neste mês" — isso é um alerta que você quer receber
    automaticamente, ou algo que você prefere caçar manualmente?

### Reajuste
12. Descreva o **cálculo real** do último reajuste de um contrato coletivo grande: que
    período de sinistralidade entrou, que índice, teve teto, teve negociação?
13. Para PME pequeno, o reajuste é do **pool de risco** ou do contrato? Como isso aparece
    para o gestor?
14. O que você registraria como "**reajuste sugerido**" vs. "**reajuste aplicado**" — e
    isso teria valor para revisar depois?

### Jornada assistencial
15. Quando você olha os eventos de um beneficiário caro, você consegue enxergar um
    **encadeamento** (consulta → exame → cirurgia → internação), ou é uma lista solta? O
    encadeamento te ajudaria a agir?
16. "A despesa desse grupo não se repetiu no mês seguinte" — para você isso é boa notícia,
    sinal de alerta, ou depende? Do quê depende?

### Alertas
17. Que **três alertas** você configuraria hoje se pudesse — com que limiar? (o limiar
    revela a escala mental do gestor)
18. Um alerta que dispara todo mês para os mesmos beneficiários — útil ou ruído? Como você
    gostaria que o produto tratasse recorrência?

### Previsibilidade
19. Se o produto dissesse "a sinistralidade deste contrato tende a X% em 3 meses, com
    intervalo Y–Z", você **usaria isso em negociação**? Ou projeção sem responsável
    atrapalha?
20. O que você quer **antecipar**: o número da sinistralidade, ou o *momento* em que um
    contrato vira problema? São coisas diferentes para você?

---

## 20. Roadmap sugerido

| Fase | Conteúdo | Pré-condição | Perfil de risco |
|---|---|---|---|
| **v1.2 — "Fase B + Contrato como recorte"** | C1, C2, C3, C4, C5, C6, C15 (seção 17.1) | Nenhuma — só engenharia sobre dados existentes | Baixo (igual v1.1) |
| **Discovery R — Receita granular** (paralelo à v1.2) | Entrevistas Q4–Q6; decidir grão de `receitas_contrato`, método de atribuição por beneficiário, nomenclatura (Q6, C9) | 1–2 entrevistas com gestor/atuária | Análise, sem código |
| **Discovery J — Reajuste** (paralelo) | Roteiro da seção 10.2; produzir `docs/DISCOVERY_REAJUSTE.md` | Entrevistas Q7–Q14 | Análise, sem código |
| **v1.3 — "Contract Intelligence"** | C7 (sinistralidade por contrato) + massa sintética com N contratos/plano (seção 14.1) + cenários C, D, H, I | Discovery R concluído; `receitas_contrato` como dado de entrada | Médio |
| **v1.4 — "Resultado assistencial"** | C8 + C10 (faixa por competência) + indicadores de resultado no catálogo de alertas | Discovery R + decisão de nomenclatura + validação de uso | Médio-Alto (risco de interpretação) |
| **v1.5 — "Sinais / Projeção"** | C13 (sinais de deterioração) e/ou C12 (projeção estatística com IC) | Discovery de previsibilidade (Q19–Q20) confirmando apetite | Médio-Alto |
| **v2.0 — "Reajuste"** | Módulo do F1 §5, com as metodologias que o Discovery J determinar | `DISCOVERY_REAJUSTE.md` + autenticação básica (dívida da v1.1) | Alto |
| **Fora de roadmap** | C16 (ML de alto custo individual), C17 (registro de decisão) até haver demanda validada | — | — |

Regra: **nenhuma fase depois da v1.2 começa sem o discovery correspondente fechado.**

---

## 21. Hipóteses que ainda precisam ser validadas

| # | Hipótese | Como testar | Risco se estiver errada |
|---|---|---|---|
| H1 | O cliente tem contraprestação **por contrato** disponível para análise | Q4 em entrevista + amostra de dados | Contract Intelligence com receita cai; fica só a versão sem sinistralidade própria |
| H2 | Gestores querem **resultado por beneficiário** mesmo sabendo que a receita é rateada | Q6 | Construímos C8 e ninguém usa; pior, alguém usa errado |
| H3 | "Resultado assistencial" / "relação despesa-receita" são **nomes aceitáveis** | Q6/Q7, mostrar mock | Retrabalho de rótulos; ruído com a área técnica do cliente |
| H4 | Contrato merece **tela própria**, não só filtro | Q9 | Construímos `/contratos` e o gestor prefere filtrar a tela de sinistralidade |
| H5 | O tema **reajuste** tem regra suficientemente estável para virar produto | Discovery J | Módulo vira consultoria sob medida por cliente, não produto |
| H6 | Há **apetite** por projeção estatística sem "dono" do número | Q19 | Construímos C12 e vira fonte de discussão política, não de decisão |
| H7 | Distinguir **episódio vs. crônico** é possível com os dados do cliente (autorização, CID) | Q10 + amostra | "Jornada" fica na timeline visual, sem classificação |
| H8 | A dupla menção (F1 + F2) a reajuste/contrato reflete um padrão do setor, **não** só a visão de dois profissionais | 3ª e 4ª entrevistas com perfis diferentes (atuária, regulatório, comercial) | Priorizamos contrato/reajuste acima do que o mercado realmente pede |
| H9 | Propagar glosa/coparticipação às dimensões **não** degrada a performance do drill | Benchmark com 20k e 100k beneficiários | Precisa materialização adicional (custo de manutenção) |
| H10 | O motor de coortes atual responde bem quando **filtrado por contrato + dimensão** juntos | Teste com `s4`/`s8` reescopados | Precisa de um caminho de consulta novo, não só um filtro |

---

## 22. Recomendação para a próxima evolução do W2Health

1. **Confirmar a tese, restringir o escopo.** O produto é *decision intelligence* sobre
   sinistralidade. O feedback 2 não muda isso — reforça que a explicação precisa de duas
   metades (causa assistencial + estrutura financeira/contratual). Construir a segunda
   metade **com os dados que já temos** antes de perseguir dados novos.

2. **Fazer a v1.2 "Fase B + Contrato como recorte"** (seção 17.1): despesa líquida em
   todos os níveis, concentração de beneficiários no topo da explicação, filtro de
   contrato, tela de contrato sem receita própria. Baixo risco, alto valor, nenhum dado
   novo, nenhuma escrita nova.

3. **Rodar dois discoveries em paralelo, sem código:** Receita granular (o gargalo real de
   dados) e Reajuste (a regra de negócio desconhecida). A dupla menção sobe a prioridade
   do *discovery*, não da construção.

4. **Tratar previsibilidade como projeção estatística com intervalo de confiança**, nunca
   como modelo preditivo, e **nunca no nível do indivíduo**. Validar apetite antes.

5. **Adotar a linguagem modular** (Executive / Loss Ratio / Contract / Beneficiary /
   Provider / Alerts Intelligence) como organização de roadmap e navegação — sem quebrar o
   monólito, sem criar seis áreas de código.

6. **Proteger o produto do inchaço:** toda tela ou bloco novo tem que responder a uma
   pergunta de decisão da lista da seção 15.2. Se só mostra mais um dado, não entra.

---

## MATRIZ DE APRENDIZADO DO PRODUTO

| Tema | Feedback 1 | Feedback 2 | Estado atual | Nossa hipótese | Confiança | Próximo passo |
|---|---|---|---|---|---|---|
| Explicação profunda (porquê do porquê) | Solicitado | Reforçado (quem provoca + relação financeira) | Feito no nível de despesa (coortes FATO/HIPÓTESE) | Falta acoplar a metade financeira/contratual à mesma árvore | Alta | Implementar C1–C3 na v1.2 |
| Composição financeira bruta → líquida | Solicitado (entregue nível operadora) | Reforçado (mesmo cálculo no beneficiário) | Só no nível operadora | Propagar às `agg_*` (Fase B) é engenharia sobre dado existente | Alta | Implementar C2 na v1.2 |
| Beneficiário como dimensão da explicação | Parcial (folha do drill) | Solicitado (dimensão de entrada) | Coortes no drill; lista por custo | Trazer concentração da variação para o 1º nível | Alta | Implementar C1 na v1.2 |
| Contrato como unidade | Introduzido como dimensão | Elevado a possível módulo | Dimensão de despesa; sem receita própria | Tela de contrato agora; módulo depois de receita + discovery reajuste | Média-Alta | C4 na v1.2; validar H4 |
| Receita por contrato | Insumo do motor de reajuste | Dimensão analítica própria | Não existe (receita é por plano; 1:1 sintético é coincidência) | É dado de entrada do cliente, não derivável | Média | Discovery R (Q4–Q5) |
| Receita por beneficiário | Não citado | Solicitado (resultado assistencial) | Não existe; sem metodologia | Sempre será atribuição/rateio, com método declarado; risco de interpretação alto | Baixa-Média | Discovery R (Q6) antes de qualquer código |
| Nomenclatura de indicadores micro | Não citado | Solicitado (nomes neutros, a validar) | Inexistente | "Resultado assistencial" / "relação despesa-receita" provisórios | Baixa | 1 pergunta de entrevista (Q6/Q7) |
| Reajuste contratual | Solicitado (proposta técnica detalhada) | Reforçado (fim da jornada do contrato) | Não existe; sem meta/data-base/histórico | Pode ser módulo de inteligência contratual — regra de negócio ainda desconhecida | Média (no tema) / Baixa (na regra) | `DISCOVERY_REAJUSTE.md` (roteiro §10.2) |
| Previsibilidade | Não citado | Solicitado (antecipar deterioração) | Não existe; motor é retrospectivo | Projeção estatística com IC + "sinais de deterioração"; nunca ML, nunca indivíduo | Baixa-Média | Validar apetite (Q19–Q20) antes de construir |
| Modelo preditivo de beneficiário de alto custo | Não citado | Implícito ("beneficiários com potencial de alto custo") | Não existe | Dados insuficientes + risco ético/regulatório alto | Baixa | Não priorizar; talvez nunca no nível individual |
| Alertas configuráveis | Solicitado | Implícito (alto impacto, novos casos) | Feito (`regras_alerta` + catálogo fechado) | Falta indicador de resultado assistencial e de concentração de contrato | Alta | Implementar C6 na v1.2 |
| Jornada assistencial encadeada | Parcial (timeline simplificada) | Reforçado (sequência de eventos) | Timeline visual, sem encadeamento de episódio | Distinguir episódio de crônico depende de dado de autorização/CID do cliente | Baixa-Média | Validar H7 (Q10, Q15) |
| Organização modular do produto | Não citado | Sugerido (6 capacidades nomeadas) | Navegação por entidade; `analytics/` já modular | Serve como linguagem de roadmap/navegação, não como produtos separados | Média | Adotar já (C15); alternativa por "pergunta de decisão" em §15.2 |
| Registro de decisão / ação | Não citado | Implícito (último nó: "ação/decisão") | Não modelado | Produto explica mas não acompanha o que foi feito | Baixa | Não priorizar até haver demanda |
| Faixa etária por competência | Não citado | Implícito (rateio por faixa, VCMH) | Fixada no seed | Pré-requisito de rateio de receita por faixa e de leitura de VCMH | Média | Roadmap (pré-req de C8) |
| Motivo de saída do beneficiário | Não citado | Não citado | Só `data_saida` / `status` | Muda a leitura de "a despesa não se repetiu" nas coortes | Baixa | Roadmap; pedir no contrato de dados do cliente |
