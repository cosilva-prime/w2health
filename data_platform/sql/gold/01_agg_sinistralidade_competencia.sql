-- gold.agg_sinistralidade_competencia  <-  silver.evento_assistencial + silver.receita
-- Espelha backend/app/seed/aggregate.py (bloco "sinistralidade por competência").
-- Parâmetro: :tenant_id

INSERT INTO gold.agg_sinistralidade_competencia (
    tenant_id, competencia, receita, despesa_bruta, glosas, coparticipacao, despesa_liquida,
    sinistralidade_bruta, sinistralidade_liquida, beneficiarios_ativos,
    exposicao_beneficiario_mes, eventos, custo_pmpm, receita_media_beneficiario
)
SELECT
    :tenant_id::varchar,
    c.competencia,
    coalesce(rc.receita, 0),
    coalesce(ev.despesa_bruta, 0),
    coalesce(ev.glosas, 0),
    coalesce(ev.coparticipacao, 0),
    coalesce(ev.despesa_liquida, 0),
    CASE WHEN coalesce(rc.receita,0) > 0 THEN coalesce(ev.despesa_bruta,0)  / rc.receita * 100 ELSE 0 END,
    CASE WHEN coalesce(rc.receita,0) > 0 THEN coalesce(ev.despesa_liquida,0)/ rc.receita * 100 ELSE 0 END,
    coalesce(rc.expo, 0),
    coalesce(rc.expo, 0),
    coalesce(ev.eventos, 0),
    CASE WHEN coalesce(rc.expo,0) > 0 THEN coalesce(ev.despesa_liquida,0) / rc.expo ELSE 0 END,
    CASE WHEN coalesce(rc.expo,0) > 0 THEN coalesce(rc.receita,0)         / rc.expo ELSE 0 END
FROM (SELECT DISTINCT competencia FROM silver.evento_assistencial WHERE tenant_id = :tenant_id
      UNION SELECT DISTINCT competencia FROM silver.receita WHERE tenant_id = :tenant_id) c
LEFT JOIN (
    SELECT competencia,
           sum(receita_contraprestacao) AS receita,
           sum(quantidade_beneficiarios) AS expo
    FROM silver.receita WHERE tenant_id = :tenant_id GROUP BY competencia
) rc ON rc.competencia = c.competencia
LEFT JOIN (
    SELECT competencia,
           sum(valor_apresentado)                                        AS despesa_bruta,
           sum(valor_glosado)                                            AS glosas,
           sum(valor_coparticipacao)                                     AS coparticipacao,
           sum(valor_apresentado - valor_glosado - valor_coparticipacao) AS despesa_liquida,
           count(*)                                                      AS eventos
    FROM silver.evento_assistencial WHERE tenant_id = :tenant_id GROUP BY competencia
) ev ON ev.competencia = c.competencia;
