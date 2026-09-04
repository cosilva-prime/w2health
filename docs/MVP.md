# MVP — W2Health Intelligence

> **Este documento descreve o MVP original.** A v1.1 aprofundou a árvore de explicação
> (coortes de beneficiários, composição financeira bruta/líquida, alertas configuráveis)
> sem alterar a tese nem remover nada aqui descrito — ver [V1.1.md](V1.1.md).

## Tese

> "Uma plataforma capaz de identificar e explicar automaticamente as principais causas das
> variações da sinistralidade de uma operadora de saúde, correlacionando informações
> financeiras e assistenciais até o nível de prestadores, procedimentos e beneficiários."

## Objetivo da demonstração

Um executivo começa em **"minha sinistralidade aumentou"** e navega até:
o que causou, quais grupos/procedimentos/prestadores contribuíram, quais beneficiários e
eventos estão envolvidos, e **se o aumento foi por frequência, por custo médio ou ambos** —
recebendo insights derivados matematicamente dos dados.

## Escopo entregue

| Área | Entregue |
|---|---|
| **Visão Executiva** | Receita, despesa assistencial, sinistralidade, beneficiários, custo assistencial PMPM, receita média PMPM. Evolução mensal, comparação MoM e YoY, acumulado 12 meses. Bloco "Principais fatores de atenção" (insights) e top grupos de despesa por contribuição. |
| **Explicação da sinistralidade** | Decomposição da variação (p.p.) em **efeito-despesa vs efeito-receita**. Decomposição da variação da despesa por 9 dimensões (grupo de despesa, tipo de atendimento, especialidade, procedimento, prestador, região, faixa etária, sexo, plano). Bridge **frequência × custo médio** por fator (Bennet simétrico, com Laspeyres como alternativa). Drill-down: sub-bridge + "onde investigar primeiro" (prestadores e beneficiários da célula). |
| **Prestadores** | Ranking de contribuição para a variação da despesa (alta/baixa). Lista completa do mês. Detecção de comportamento **fora do padrão** (z-score vs pares da mesma especialidade). Detalhe do prestador: KPIs, série, principais procedimentos, concentração (Pareto/Gini), bridge, comparação com pares. |
| **Beneficiários** | Lista anonimizada por custo, com filtros (faixa etária, sexo). Busca por identificador sintético (`BEN-000001`). Detalhe: perfil, evolução mensal de custo, tabela de eventos e **timeline assistencial simplificada** (Consulta → Exame → Diagnóstico → Procedimento → Internação → Retorno). |
| **Insights automáticos** | Motor de regras sobre os cálculos: variação da sinistralidade, efeito da receita, fator dominante (especialidade/grupo) com bridge, internações MoM, concentração em prestadores, prestador fora do padrão, concentração em beneficiários, redução/melhora, sazonalidade. Cada insight: severidade, métricas de suporte, `deep_link` para a tela e **metodologia** (a fórmula). |
| **Dados sintéticos** | 20.000 beneficiários (parametrizável até 100.000), 24 meses (jan/2025–dez/2026), ~120 prestadores, ~85 procedimentos, 15 especialidades, 12 planos, ~40 diagnósticos, ~320 mil eventos. Reprodutível por seed. 9 cenários intencionais com gabarito. |
| **Testes** | Fórmulas (sinistralidade, %, p.p., custo médio, frequência, contribuição, Bennet, Laspeyres, concentração, Gini). Detecção dos 9 cenários. Endpoints críticos. |

## Critério de sucesso (teste de aceitação)

Executar a narrativa completa usando o **cenário de catarata**:

1. sinistralidade aumentou → magnitude da variação;
2. explicar principais drivers;
3. identificar procedimento relevante (facectomia/catarata);
4. identificar prestadores responsáveis;
5. chegar aos beneficiários/eventos;
6. separar efeito frequência de efeito custo médio;
7. produzir insight textual consistente com os cálculos.

O motor deve reencontrar o cenário plantado pelo gerador (comparação com `cenarios_gabarito`).
Ver `tests/test_scenarios.py::test_cataract_frequency_scenario_detected` e o roteiro em
[DEMO.md](DEMO.md).

## Fora do escopo (roadmap)

Mobile; integrações reais (MV, Tasy, Benner, TISS); dados reais; LLM/chatbot; ML complexo;
recomendação clínica; automação de decisão médica; multi-tenant completo; billing; cloud
definitiva; autenticação (o MVP roda sem login, com o banner de ambiente demonstrativo).
Efeito **mix** na decomposição de grupos coesos é aproximado pela soma dos bridges por
procedimento — um modelo 3-vias (frequência/preço/mix) fica no roadmap.
