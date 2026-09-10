-- gold.agg_contrato_competencia  <-  gold.agg_beneficiario_competencia + silver.beneficiario
-- Contract Intelligence (v1.2). SEM receita/sinistralidade próprias.
-- Espelha o bloco "contrato x competência" de backend/app/seed/aggregate.py.
-- Parâmetros: :tenant_id, :alto_custo_mes (limiar R$/mês de "beneficiário de alto custo")

INSERT INTO gold.agg_contrato_competencia (
    tenant_id, competencia, id_contrato, vidas,
    despesa, despesa_bruta, glosas, coparticipacao, despesa_liquida,
    eventos, beneficiarios_com_evento, custo_pmpm, gini, top5_share, n_beneficiarios_alto_custo
)
WITH vidas AS (
    SELECT c.competencia, b.id_contrato, count(*) AS vidas
    FROM (SELECT DISTINCT competencia FROM gold.agg_beneficiario_competencia WHERE tenant_id = :tenant_id) c
    JOIN silver.beneficiario b
      ON b.tenant_id = :tenant_id
     AND b.data_adesao <= c.competencia
     AND (b.data_saida IS NULL OR b.data_saida > c.competencia)
    GROUP BY c.competencia, b.id_contrato
),
ben AS (
    SELECT ac.competencia, ac.id_contrato,
           ac.despesa, ac.despesa_bruta, ac.glosas, ac.coparticipacao, ac.despesa_liquida, ac.eventos,
           row_number() OVER (PARTITION BY ac.competencia, ac.id_contrato ORDER BY ac.despesa_liquida ASC)  AS rnk_asc,
           row_number() OVER (PARTITION BY ac.competencia, ac.id_contrato ORDER BY ac.despesa_liquida DESC) AS rnk_desc
    FROM gold.agg_beneficiario_competencia ac
    WHERE ac.tenant_id = :tenant_id AND ac.despesa_liquida > 0
),
ctr AS (
    SELECT competencia, id_contrato,
           sum(despesa) AS despesa, sum(despesa_bruta) AS despesa_bruta,
           sum(glosas) AS glosas, sum(coparticipacao) AS coparticipacao,
           sum(despesa_liquida) AS despesa_liquida, sum(eventos) AS eventos,
           count(*) AS n_ben,
           sum(rnk_asc * despesa_liquida) AS srv,
           sum(despesa_liquida) FILTER (WHERE rnk_desc <= 5) AS top5,
           count(*) FILTER (WHERE despesa_liquida >= :alto_custo_mes) AS n_alto
    FROM ben GROUP BY competencia, id_contrato
)
SELECT :tenant_id::varchar, v.competencia, v.id_contrato, v.vidas,
       coalesce(ctr.despesa,0), coalesce(ctr.despesa_bruta,0), coalesce(ctr.glosas,0),
       coalesce(ctr.coparticipacao,0), coalesce(ctr.despesa_liquida,0), coalesce(ctr.eventos,0),
       coalesce(ctr.n_ben,0),
       CASE WHEN v.vidas > 0 THEN coalesce(ctr.despesa_liquida,0) / v.vidas ELSE 0 END,
       CASE WHEN coalesce(ctr.n_ben,0) > 0 AND coalesce(ctr.despesa_liquida,0) > 0
            THEN (2.0 * ctr.srv) / (ctr.n_ben * ctr.despesa_liquida) - (ctr.n_ben + 1.0) / ctr.n_ben
            ELSE 0 END                                                         AS gini,
       CASE WHEN coalesce(ctr.despesa_liquida,0) > 0
            THEN coalesce(ctr.top5,0) / ctr.despesa_liquida ELSE 0 END          AS top5_share,
       coalesce(ctr.n_alto,0)
FROM vidas v
LEFT JOIN ctr ON ctr.competencia = v.competencia AND ctr.id_contrato = v.id_contrato;
