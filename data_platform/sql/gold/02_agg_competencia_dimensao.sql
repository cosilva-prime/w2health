-- gold.agg_competencia_dimensao  <-  silver.evento_assistencial (+ catálogos)
-- Uma dimensão por execução (:dimensao). Espelha o loop de backend/app/seed/aggregate.py.
-- `despesa` = Σ valor_pago (bruta − glosa). As 4 colunas de composição são aditivas (v1.2).
-- Exemplo abaixo: dimensão = 'especialidade'. Trocar o JOIN/chave/rotulo por dimensão.
-- Parâmetro: :tenant_id

INSERT INTO gold.agg_competencia_dimensao (
    tenant_id, competencia, dimensao, chave, rotulo,
    despesa, despesa_bruta, glosas, coparticipacao, despesa_liquida,
    eventos, quantidade, beneficiarios, custo_medio, freq_por_mil
)
SELECT
    :tenant_id::varchar,
    e.competencia,
    'especialidade'                             AS dimensao,
    es.id_especialidade::text                   AS chave,
    min(es.nome)                                AS rotulo,
    sum(e.valor_pago)                           AS despesa,
    sum(e.valor_apresentado)                    AS despesa_bruta,
    sum(e.valor_glosado)                        AS glosas,
    sum(e.valor_coparticipacao)                 AS coparticipacao,
    sum(e.valor_apresentado - e.valor_glosado - e.valor_coparticipacao) AS despesa_liquida,
    count(*)                                    AS eventos,
    sum(e.quantidade)                           AS quantidade,
    count(DISTINCT e.id_beneficiario)           AS beneficiarios,
    CASE WHEN count(*) > 0 THEN sum(e.valor_pago) / count(*) ELSE 0 END AS custo_medio,
    CASE WHEN s.exposicao_beneficiario_mes > 0
         THEN count(*)::float / s.exposicao_beneficiario_mes * 1000 ELSE 0 END AS freq_por_mil
FROM silver.evento_assistencial e
JOIN silver.especialidade es
     ON es.tenant_id = e.tenant_id AND es.id_especialidade = e.id_especialidade
JOIN gold.agg_sinistralidade_competencia s
     ON s.tenant_id = e.tenant_id AND s.competencia = e.competencia
WHERE e.tenant_id = :tenant_id
GROUP BY e.competencia, es.id_especialidade, s.exposicao_beneficiario_mes;
