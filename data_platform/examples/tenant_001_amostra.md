# Amostra do modelo canônico — `tenant_id = "operadora-alfa"`

Linhas fictícias ilustrando o layout Silver. Formato só para leitura humana.

## beneficiario
| tenant_id | id_beneficiario | codigo | data_nascimento | sexo | id_plano | id_contrato | data_adesao | data_saida | status |
|---|---|---|---|---|---|---|---|---|---|
| operadora-alfa | 84213 | BEN-000123 | 1961-04-12 | F | 12 | 45 | 2019-03-01 | | ativo |
| operadora-alfa | 84880 | BEN-000882 | 1978-11-02 | M | 12 | 45 | 2021-07-01 | 2026-05-01 | inativo |

## contrato
| tenant_id | id_contrato | codigo | id_plano | nome | tipo |
|---|---|---|---|---|---|
| operadora-alfa | 45 | CT-2019-0456 | 12 | Indústria Metalúrgica XYZ | Empresarial |

## evento_assistencial
| tenant_id | id_evento | source_record_id | id_beneficiario | id_contrato | id_prestador | id_procedimento | data_evento | competencia | tipo_atendimento | valor_apresentado | valor_glosado | valor_coparticipacao | valor_pago | despesa_liquida |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| operadora-alfa | 88123901 | CTA-2026-7788/03 | 84213 | 45 | 3110 | 1162 | 2026-07-14 | 2026-07-01 | cirurgia | 4200.00 | 180.00 | 0.00 | 4020.00 | 4020.00 |
| operadora-alfa | 88124440 | CTA-2026-7791/01 | 84213 | 45 | 3110 | 90 | 2026-07-16 | 2026-07-01 | consulta | 220.00 | 0.00 | 66.00 | 220.00 | 154.00 |

## receita
| tenant_id | competencia | id_plano | quantidade_beneficiarios | receita_contraprestacao |
|---|---|---|---|---|
| operadora-alfa | 2026-07-01 | 12 | 1840 | 6620000.00 |

## receita_contrato  *(layout preparado — vazio na v1.2)*
| tenant_id | competencia | id_contrato | quantidade_beneficiarios | receita_contraprestacao | metodologia |
|---|---|---|---|---|---|
| operadora-alfa | 2026-07-01 | 45 | 312 | 198000.00 | faturado_contrato |
