# Decisões do MVP — W2Health Intelligence

> Estas são **decisões desta versão do MVP**, tomadas para permitir avançar de forma
> incremental. **Não** são decisões arquiteturais definitivas do produto — todas podem ser
> revistas nas próximas fases sem prejuízo do que já foi construído.

Data da aprovação: 2026-09-02

| # | Tema | Decisão do MVP | Observação |
|--:|------|----------------|------------|
| 1 | Repositório | W2Health é um **projeto/repositório novo e independente** (`projetos/w2health/`). | Sem acoplamento com o SweetERP; apenas convenções de stack reaproveitadas. |
| 2 | Massa de dados sintéticos | Default **20.000 beneficiários**, com geração **parametrizável** para 100.000. | Parâmetro no gerador (Etapa 3/4). |
| 3 | Biblioteca de gráficos | **Recharts**. | Reavaliável se surgir necessidade de visualização mais sofisticada. |
| 4 | Autenticação | MVP **sem autenticação**. Manter o banner **“Ambiente demonstrativo — dados sintéticos”** visível. | `login` demo / JWT ficam no roadmap. |
| 5 | Comparação padrão | **Mês anterior (MoM)** como comparação default. Demais opções previstas (mesmo mês do ano anterior, acumulado 12 meses) permanecem no escopo. | — |
| 6 | Bridge frequência × custo médio | **Bennet simétrico** como método padrão (soma dos efeitos = ΔD, sem resíduo). | Laspeyres disponível como visão alternativa. |
| 7 | Framework de frontend | **Next.js com App Router**. | TypeScript + Tailwind conforme planejamento. |

## Itens explicitamente adiados (roadmap)

Mobile, integrações reais (MV, Tasy, Benner, TISS), ML/LLM, chatbot, recomendação clínica,
billing real, multi-tenant completo, infraestrutura cloud. Ver seção 11 do
[planejamento](00-PLANEJAMENTO-MVP.md).
