-- silver.beneficiario  <-  raw.beneficiario (já com colunas canônicas via mapping)
-- Contrato: data_platform/contracts/beneficiario.yaml
-- Parâmetro: :tenant_id

INSERT INTO silver.beneficiario (
    tenant_id, id_beneficiario, codigo, data_nascimento, sexo,
    id_plano, id_contrato, data_adesao, data_saida, motivo_saida, status,
    source_system, source_record_id, ingestion_id, ingestion_timestamp,
    source_updated_at, raw_payload_hash
)
SELECT
    r.tenant_id,
    -- surrogate estável a partir da business key (nunca CPF/CNS)
    ('x' || substr(md5(r.tenant_id || '|' || r.codigo), 1, 15))::bit(60)::bigint AS id_beneficiario,
    r.codigo,
    r.data_nascimento,
    nullif(upper(trim(r.sexo)), '')                                    AS sexo,
    pl.id_plano,
    ct.id_contrato,
    r.data_adesao,
    r.data_saida,
    nullif(lower(trim(r.motivo_saida)), '')                            AS motivo_saida,
    CASE WHEN r.data_saida IS NULL OR r.data_saida > current_date
         THEN 'ativo' ELSE 'inativo' END                              AS status,
    r.source_system, r.source_record_id, r.ingestion_id, r.ingestion_timestamp,
    r.source_updated_at, r.raw_payload_hash
FROM raw.beneficiario r
LEFT JOIN silver.plano    pl ON pl.tenant_id = r.tenant_id AND pl.codigo = r.plano_codigo
LEFT JOIN silver.contrato ct ON ct.tenant_id = r.tenant_id AND ct.codigo = r.contrato_codigo
WHERE r.tenant_id = :tenant_id
ON CONFLICT (tenant_id, codigo) DO UPDATE SET
    data_nascimento = EXCLUDED.data_nascimento,
    sexo            = EXCLUDED.sexo,
    id_plano        = EXCLUDED.id_plano,
    id_contrato     = EXCLUDED.id_contrato,
    data_adesao     = EXCLUDED.data_adesao,
    data_saida      = EXCLUDED.data_saida,
    motivo_saida    = EXCLUDED.motivo_saida,
    status          = EXCLUDED.status,
    source_updated_at = EXCLUDED.source_updated_at
WHERE EXCLUDED.source_updated_at IS NULL
   OR silver.beneficiario.source_updated_at IS NULL
   OR EXCLUDED.source_updated_at >= silver.beneficiario.source_updated_at;
