# Capability Readiness — W2Health (v1.2)

> Nem todo cliente tem todos os dados. Este documento define, para cada capacidade, o que
> é **obrigatório**, o que é **desejável**, e **o que acontece se faltar** — para decidir
> quais módulos habilitar no onboarding de cada operadora.

## Modelo conceitual

Para um tenant, cada capacidade tem um estado:

- ✅ **Pronta** — todos os dados obrigatórios presentes e com qualidade (sem `ERROR` de DQ).
- 🟡 **Parcial** — obrigatórios presentes, faltam desejáveis → habilita com aviso/limitação.
- ❌ **Indisponível** — falta dado obrigatório → módulo escondido.

Avaliação (conceitual): sobre a Silver carregada do tenant, checar presença/preenchimento
das entidades/campos abaixo + resultado da Data Quality.

## Matriz

| Capacidade | Dados OBRIGATÓRIOS | Dados DESEJÁVEIS | Resultado se faltar obrigatório | Se faltar só desejável |
|---|---|---|---|---|
| **Executive Intelligence** (visão da carteira) | receita (competência, valor, vidas) + evento (valor_pago, competência) | — | ❌ sem sinistralidade | — |
| **Loss Ratio Intelligence** (explicar a variação) | + evento com especialidade, procedimento, tipo_atendimento | glosa/coparticipação por evento | ❌ sem decomposição por driver | 🟡 sem separar glosa/copart nos drivers |
| **Provider Intelligence** | + prestador; evento com id_prestador | prestador.id_especialidade_principal | ❌ | 🟡 sem detecção de anomalia vs pares (z-score) |
| **Beneficiary Intelligence** | + evento por beneficiário; beneficiário | data_adesao/data_saida; perfil_utilizacao | ❌ | 🟡 sem coortes "novos/saíram"; hipótese de episódio vira "a investigar" |
| **Contract Intelligence** (`/contratos`) | + contrato; beneficiário.id_contrato | — | ❌ módulo escondido | — |
| **Contrato — sinistralidade própria** | receita_contrato (competência × contrato) | — | ❌ (v1.2: sempre indisponível) | — |
| **Explicação por glosa** | valor_glosado por evento | motivo_glosa | 🟡 assume glosa = 0 | 🟡 sem "explicação por motivo" |
| **Explicação por coparticipação** | valor_coparticipacao por evento **ou** plano.percentual_coparticipacao | origem_dado (faturada/derivada) | 🟡 assume copart = 0 | 🟡 número marcado "estimado" |
| **Coortes (o porquê do porquê)** | beneficiário + evento + data_adesao/data_saida | perfil_utilizacao do procedimento | 🟡 só "novos/recorrentes/deixaram de usar" | 🟡 hipótese de episódio pontual não é levantada |
| **Concentração de beneficiários (C1)** | evento por beneficiário; despesa_liquida | — | ❌ | — |
| **Descritores de comportamento (C5)** | série mensal do beneficiário (agg_beneficiario) | — | ❌ | — |
| **Alertas configuráveis** | qualquer capacidade acima habilitada | — | herda das capacidades | — |
| **Reajuste contratual** | receita_contrato + contrato.data_base/meta + histórico | VCMH, RN aplicável | ❌ (fora do escopo v1.2 — discovery pendente) | — |
| **Previsibilidade / projeção** | ≥ 24 meses de série contínua e consistente | — | ❌ (fora do escopo v1.2) | — |

## Exemplo de leitura para um tenant

```
Cliente possui:
  eventos ✅   beneficiários ✅   prestadores ✅   receita por plano ✅
  valor_glosado por evento ✅     valor_coparticipacao por evento ❌ (só % do plano)
  beneficiário.id_contrato ✅     receita por contrato ❌

Resultado:
  Executive Intelligence          ✅
  Loss Ratio Intelligence         ✅
  Provider Intelligence           ✅
  Beneficiary Intelligence        ✅
  Contract Intelligence           🟡  (sem sinistralidade contratual — só vidas/despesa/concentração)
  Explicação por glosa            ✅
  Explicação por coparticipação   🟡  (derivada da regra do plano — marcada "estimada")
  Reajuste                        ❌
```

## Onde isso viveria

Na Fase 2, `source_entities` + uma tabela `tenant_capabilities` (tenant × capacidade ×
estado × motivo) alimentada por uma checagem pós-carga. Na v1.2 é este documento + a
avaliação manual no onboarding.
