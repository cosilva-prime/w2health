-- silver.evento_assistencial  <-  raw.evento_assistencial (colunas canônicas via mapping)
-- Contrato: data_platform/contracts/evento_assistencial.yaml
-- Parâmetro: :tenant_id
--
-- Regras aplicadas aqui:
--  * valor_pago  = coalesce(origem, valor_apresentado - valor_glosado)
--  * valor_coparticipacao = coalesce(origem, regra do plano p/ tipos elegíveis)
--  * despesa_liquida = valor_apresentado - valor_glosado - valor_coparticipacao (derivada)
--  * id_contrato: do beneficiário (ou histórico de vínculo, se disponível)

INSERT INTO silver.evento_assistencial (
    tenant_id, id_evento, source_record_id, id_beneficiario, id_contrato, id_prestador,
    id_procedimento, id_especialidade, id_diagnostico, data_evento, competencia,
    tipo_atendimento, quantidade, valor_apresentado, valor_glosado, valor_coparticipacao,
    valor_pago, despesa_liquida,
    source_system, ingestion_id, ingestion_timestamp, source_updated_at, raw_payload_hash
)
SELECT
    r.tenant_id,
    ('x' || substr(md5(r.tenant_id || '|' || r.source_system || '|' || r.source_record_id), 1, 15))::bit(60)::bigint,
    r.source_record_id,
    b.id_beneficiario,
    b.id_contrato,
    pr.id_prestador,
    pc.id_procedimento,
    coalesce(es.id_especialidade, pc.id_especialidade),
    dg.id_diagnostico,
    r.data_evento,
    date_trunc('month', r.competencia)::date                          AS competencia,
    r.tipo_atendimento,
    coalesce(r.quantidade, 1)                                         AS quantidade,
    r.valor_apresentado,
    coalesce(r.valor_glosado, 0)                                      AS valor_glosado,
    coalesce(
        r.valor_coparticipacao,
        CASE WHEN pl.tem_coparticipacao
              AND r.tipo_atendimento IN ('consulta','exame','terapia','pronto_socorro')
             THEN round(coalesce(r.valor_pago, r.valor_apresentado - coalesce(r.valor_glosado,0))
                        * pl.percentual_coparticipacao, 2)
             ELSE 0 END
    )                                                                 AS valor_coparticipacao,
    coalesce(r.valor_pago, r.valor_apresentado - coalesce(r.valor_glosado, 0)) AS valor_pago,
    r.valor_apresentado
      - coalesce(r.valor_glosado, 0)
      - coalesce(r.valor_coparticipacao, 0)                           AS despesa_liquida,
    r.source_system, r.ingestion_id, r.ingestion_timestamp, r.source_updated_at, r.raw_payload_hash
FROM raw.evento_assistencial r
JOIN silver.beneficiario  b  ON b.tenant_id = r.tenant_id AND b.codigo = r.beneficiario_codigo
JOIN silver.plano         pl ON pl.id_plano = b.id_plano
JOIN silver.prestador     pr ON pr.tenant_id = r.tenant_id AND pr.codigo = r.prestador_codigo
JOIN silver.procedimento  pc ON pc.tenant_id = r.tenant_id AND pc.codigo = r.procedimento_codigo
LEFT JOIN silver.especialidade es ON es.tenant_id = r.tenant_id AND es.codigo = r.especialidade_codigo
LEFT JOIN silver.diagnostico   dg ON dg.tenant_id = r.tenant_id AND dg.cid = r.cid
WHERE r.tenant_id = :tenant_id
ON CONFLICT (tenant_id, source_system, source_record_id) DO UPDATE SET
    valor_apresentado    = EXCLUDED.valor_apresentado,
    valor_glosado        = EXCLUDED.valor_glosado,
    valor_coparticipacao = EXCLUDED.valor_coparticipacao,
    valor_pago           = EXCLUDED.valor_pago,
    despesa_liquida      = EXCLUDED.despesa_liquida,
    source_updated_at    = EXCLUDED.source_updated_at;   -- glosa tardia / reversão
