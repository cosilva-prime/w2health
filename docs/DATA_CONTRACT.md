# Data Contract inicial — W2Health (v1.2)

O que o W2Health **espera receber** de uma operadora, classificado por criticidade.
Fonte de verdade campo-a-campo: `data_platform/contracts/*.yaml`. Este documento resume
para conversar com o engenheiro de dados do cliente.

## Classificação

- **OBRIGATÓRIO** — sem isto o W2Health não liga a capacidade correspondente.
- **RECOMENDADO** — a capacidade funciona sem, mas perde profundidade/precisão.
- **OPCIONAL** — habilita capacidade futura (reajuste, receita granular).

## Por entidade

### evento_assistencial
| Campo | Nível | Observação |
|---|---|---|
| tenant_id, source_record_id | OBRIGATÓRIO | rastreabilidade / dedup |
| id_beneficiario, id_prestador, id_procedimento | OBRIGATÓRIO | chaves da análise |
| data_evento, competencia | OBRIGATÓRIO | grão temporal (definir: competência de atendimento ou de pagamento) |
| tipo_atendimento | OBRIGATÓRIO | decomposição por tipo, bridge de internações |
| valor_apresentado, valor_pago | OBRIGATÓRIO | despesa |
| valor_glosado | RECOMENDADO | sem ele: sem "explicação por glosa"; assume 0 |
| valor_coparticipacao | RECOMENDADO | sem ele: derivado da regra do plano (marcado como estimado) |
| id_contrato | RECOMENDADO | sem ele: sem Contract Intelligence |
| id_especialidade | RECOMENDADO | senão derivado do procedimento |
| id_diagnostico (CID) | OPCIONAL | habilita análise por diagnóstico e "episódio" |

### receita
| Campo | Nível | Observação |
|---|---|---|
| competencia, id_plano, receita_contraprestacao, quantidade_beneficiarios | OBRIGATÓRIO | grão mínimo de sinistralidade |

### beneficiario
| Campo | Nível | Observação |
|---|---|---|
| tenant_id, codigo | OBRIGATÓRIO | identidade (pseudonimizada) |
| data_nascimento, id_plano | OBRIGATÓRIO | faixa etária, sinistralidade por plano |
| data_adesao, data_saida | RECOMENDADO | coortes "novos" / "saíram da carteira" |
| id_contrato | RECOMENDADO | Contract Intelligence, coortes por contrato |
| motivo_saida | RECOMENDADO | leitura correta de "a despesa não se repetiu" |

### plano
`codigo`, `nome` OBRIGATÓRIO; `segmentacao` RECOMENDADO; `tem_coparticipacao`,
`percentual_coparticipacao` RECOMENDADO (para derivar coparticipação por evento).

### contrato
`codigo`, `id_plano` OBRIGATÓRIO (se quiser Contract Intelligence); `tipo` RECOMENDADO;
`data_base`, `meta_sinistralidade` OPCIONAL (reajuste — fora do escopo v1.2).

### prestador / especialidade / procedimento
`codigo` + `nome/descricao` OBRIGATÓRIO. `prestador.id_especialidade_principal`
RECOMENDADO (grupo de pares para detecção de anomalia).
`procedimento.grupo_procedimento` / `perfil_utilizacao` RECOMENDADO (coortes).

### receita_contrato — OPCIONAL / futuro
Todo o layout é OPCIONAL na v1.2. É pré-requisito de **sinistralidade por contrato** e do
módulo de **reajuste** — ambos fora do escopo, dependem de discovery
(`docs/DISCOVERY_GESTAO_SAUDE.md`).

## Capacidade → dados (resumo — detalhe em `CAPABILITY_READINESS.md`)

| Capacidade | Dados obrigatórios |
|---|---|
| Sinistralidade geral / Executive | receita + evento (valor + competência) |
| Loss Ratio Intelligence (explicação) | + especialidade + procedimento + tipo_atendimento |
| Provider Intelligence | + prestador (com especialidade principal) |
| Beneficiary Intelligence | + beneficiário + evento por beneficiário |
| Contract Intelligence | + contrato + beneficiário↔contrato |
| Explicação por glosa | + valor_glosado por evento |
| Explicação por coparticipação | + valor_coparticipacao por evento |
| Coortes (o porquê do porquê) | + data_adesao/data_saida + perfil_utilizacao |
| Alertas configuráveis | nada além do acima |
| Sinistralidade por contrato / Reajuste | receita_contrato (**não disponível na v1.2**) |

## Fase 2 — o contrato em uso

- Contrato **operacional** v1 (o que a carga de arquivo exige hoje):
  `backend/app/data_platform/canonical.py`, explicado em
  [MAPPING_FRAMEWORK.md](MAPPING_FRAMEWORK.md) §6 (inclui as diferenças deliberadas em
  relação a este documento, ex.: cidade/UF do prestador obrigatórias).
- Para o cliente, em linguagem de negócio: [CLIENT_DATA_REQUIREMENTS.md](CLIENT_DATA_REQUIREMENTS.md).
- O contrato é aplicado por um mapping versionado por fonte; uma violação vira resultado
  de Data Quality com linha e motivo ([DATA_QUALITY.md](DATA_QUALITY.md)).
- Receita por plano continua opcional **no pacote**, mas sem ela as capabilities de
  sinistralidade ficam `NOT_READY` ([CAPABILITY_READINESS.md](CAPABILITY_READINESS.md)).
- `receita_contrato` segue fora do escopo (sinistralidade por contrato indisponível).
