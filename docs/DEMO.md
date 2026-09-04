# Roteiro de demonstração — W2Health Intelligence

Público: diretoria e potenciais clientes. Duração: ~8–10 min.
Mensagem final: *"Hoje eu sei que minha sinistralidade aumentou. Com esta plataforma eu
entendo por quê — até o prestador e o beneficiário."*

## Preparação (1 min, antes da reunião)

```bash
docker compose up -d --build
docker compose exec backend python -m app.seed.run --beneficiarios 20000
# abrir http://localhost:3000
```

Deixe o filtro **Competência = Julho/2026** e **Comparar com = mês anterior**.
(A base é reprodutível — seed 42. Os números abaixo são estáveis com esse seed.)

---

## Ato 1 — "A sinistralidade aumentou" (Visão Executiva)

1. Abra a **Visão Executiva**. Aponte os KPIs: sinistralidade **~74%**, com **+3,0 p.p.**
   vs junho. Receita, despesa assistencial, beneficiários, custo por beneficiário.
2. No gráfico de evolução, mostre a linha subindo ao longo de 2026 (a faixa cinza é o
   acumulado 12 meses).
3. Texto abaixo do gráfico: *"a variação veio +2,7 p.p. de despesa e +0,3 p.p. de receita"*
   → **a alta é de despesa assistencial**.
4. Bloco **"Principais fatores de atenção"**: chips coloridos. Clique em
   **"Oftalmologia pressionou a despesa em R$ …"**.

> Frase de efeito: *"Qualquer BI mostra que subiu. A pergunta é: por quê? O sistema já
> respondeu — e é clicável."*

## Ato 2 — "Por quê?" (Sinistralidade → decomposição)

5. Você caiu na tela **Sinistralidade** já filtrada. No topo: 74,2% vs 71,2%, +3,0 p.p.
6. Card **"A variação veio de despesa ou de receita?"** — efeito despesa vs efeito receita
   (identidade exata).
7. Troque o seletor de dimensão para **Procedimento**. O **waterfall** mostra os fatores;
   a tabela lista cada um com **Δ despesa, % da variação, impacto em p.p. e o Efeito**
   (badge Frequência / Custo médio / Misto).
8. Encontre **"Facectomia com implante de LIO (catarata)"** — impacto ~**R$ 250 mil**,
   efeito **Frequência**. Clique em **investigar**.

## Ato 3 — Frequência ou custo médio? (Drill-down)

9. Painel do fator: **Efeito frequência ≈ R$ 240 mil** · **Efeito custo médio ≈ R$ 6 mil**.
   Frequência: **~57 → ~117 eventos (+103%)**. Custo médio: praticamente estável (**+3,5%**).
   → *"O aumento foi por volume de cirurgias, não por preço."*
10. Gráfico "Despesa mensal do fator": salto em julho.
11. Bloco **"Onde investigar primeiro — prestadores"**: 3 prestadores concentram
    **~100% do aumento** de catarata. Clique em um deles.

## Ato 4 — Até o beneficiário

12. Tela do **prestador**: KPIs, bridge do prestador, **comparação com pares (z-score)**,
    principais procedimentos, evolução.
13. Volte ao drill e use **"Onde investigar primeiro — beneficiários"**: clique em um
    `BEN-…`.
14. Tela do **beneficiário** (anonimizado): perfil, evolução de custo e a **timeline
    assistencial** (Consulta → Exame → Diagnóstico → Procedimento → Internação → Retorno).

## Ato 5 — Insights automáticos e rastreabilidade

15. Menu **Insights**. Mostre o feed ordenado por relevância:
    - *"A sinistralidade aumentou 3,0 p.p."*
    - *"Oftalmologia pressionou a despesa em R$ … (76% da variação) — efeito frequência"*
    - *"Hospital … apresenta comportamento fora do padrão"* (z-score vs pares)
    - *"5% dos beneficiários concentraram X% da despesa do período"*
16. Em qualquer card, clique **"Como calculamos"** — aparece a **fórmula** e as métricas.
    *"Nenhuma frase é escrita à mão. Mude o banco e os insights mudam."*

## Ato 6 — Outros cenários (opcional, 2 min)

Troque a competência e mostre que o motor acha padrões diferentes:

| Competência | O que aparece |
|---|---|
| **Set/2026** | Insight de **internações +~65%**, concentração em 60+ |
| **Jun/2026** (dimensão Procedimento) | **Ressonância magnética** com efeito **Custo médio** (frequência estável, preço +30%) — o oposto da catarata |
| **Out/2026** | Insight **positivo**: *"Sessão de fisioterapia reduziu a despesa…"* (programa de gestão, efeito frequência) |
| **Prestadores → anomalias** | Prestador de ortopedia com custo médio ~45% acima dos pares |

## Prova de que o motor "acerta o gabarito"

```bash
docker compose exec backend pytest -m scenarios -q
```
Os 13 cenários plantados pelo gerador são redescobertos pelo motor (14 asserções
verdes). O teste `test_cataract_frequency_scenario_detected` é o teste de aceitação
principal do MVP original.

---

## v1.1 — Novas funcionalidades (~5 min adicionais)

### Ato 7 — "Por que caiu?" vai um nível mais fundo (coortes)

1. Em **Sinistralidade**, mude a competência para **Out/2026**, dimensão
   **Procedimento**. Clique em **"Sessão de fisioterapia"** (fator de redução).
2. Role até a seção **"Por que Sessão de fisioterapia caiu?"**. Mostre os cartões de
   coorte: *"330 beneficiários permaneceram na carteira mas não tiveram novo evento"*
   (🟦 **Fato**, confiança alta) e *"nenhum padrão conclusivo"* (⬜ **A investigar**,
   confiança baixa) — *"o sistema não inventa que o tratamento terminou quando os dados
   não sustentam essa conclusão."*
3. Contraste com **Julho/2026 → Catarata**: aqui a mesma seção mostra uma
   **Hipótese** (confiança média) de *"conclusão de episódio pontual"* — porque
   catarata é cirurgia, não terapia recorrente. *"O motor distingue os dois casos
   automaticamente, pelo perfil clínico do procedimento."*

### Ato 8 — Composição da despesa: bruta × líquida

4. Na Visão Executiva ou em Sinistralidade, mude para **Fevereiro/2026**. Mostre a
   seção **"Composição da despesa assistencial"**: Despesa Bruta → (−) Glosas → (−)
   Coparticipação → Despesa Líquida.
5. Aponte **Sinistralidade Bruta ≈ 75,9%** vs **Sinistralidade Líquida ≈ 65,3%** —
   *"nunca mostramos só 'a sinistralidade' sem dizer qual base."*
6. Os 4 efeitos da decomposição mostram **Glosa** como o maior — *"a melhora deste mês
   veio principalmente do aumento da taxa de glosa, não de menos utilização."*

### Ato 9 — Alertas configurados pelo gestor

7. Vá em **Configuração** (`/configuracao/insights`). Crie uma regra: Entidade
   **Beneficiário**, Indicador **Participação na variação da sinistralidade**,
   Operador **>=**, Limite **0.35**, Severidade **Crítica**.
8. Vá em **Insights → 🔔 Alertas configurados**, competência **Junho/2026**. Os alertas
   aparecem com o beneficiário, o valor observado e o limite configurado — *"o alerta só
   aparece porque o dado realmente cruzou o limite; a regra literal de 50% do
   enunciado, por exemplo, não dispara nesta carteira de 20 mil vidas — e isso é
   correto, não um bug."*
9. Clique em **Investigar** para chegar ao beneficiário.

Prova objetiva:
```bash
docker compose exec backend pytest tests/test_cohorts.py tests/test_alerts.py -q
docker compose exec backend pytest -m scenarios -k "s10 or s11 or s12 or s13" -q
```
