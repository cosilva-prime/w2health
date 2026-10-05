"""Job de (re)construção da camada analítica a partir da fato bruta.

Roda inteiramente no PostgreSQL (INSERT ... SELECT ... GROUP BY) — rápido mesmo com
centenas de milhares de eventos. Chamado ao final do seed e por `python -m app.seed.aggregate`
quando os dados brutos mudam.

v1.2:
  * é **tenant-scoped** — reconstrói só o tenant informado (`tenant_id`, default `w2h-demo`);
  * `agg_competencia_dimensao`, `agg_prestador_competencia` e `agg_beneficiario_competencia`
    ganham `despesa_bruta / glosas / coparticipacao / despesa_liquida` (aditivo à `despesa`,
    que segue sendo `Σ valor_pago`);
  * nova `agg_contrato_competencia` — base de Contract Intelligence, **sem receita/
    sinistralidade próprias**.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.tenant import DEFAULT_TENANT
from app.core.thresholds import ALTO_CUSTO_MES  # limiar (R$/mês) de "beneficiário de alto custo"

# dimensao -> (join extra, expressão da chave, expressão do rótulo)
_DIMENSOES: dict[str, tuple[str, str, str]] = {
    "grupo_despesa": (
        "JOIN procedimentos pr ON pr.id = e.id_procedimento",
        "pr.grupo_procedimento",
        "pr.grupo_procedimento",
    ),
    "tipo_atendimento": ("", "e.tipo_atendimento", "e.tipo_atendimento"),
    "especialidade": (
        "JOIN especialidades es ON es.id = e.id_especialidade",
        "es.id::text",
        "es.nome",
    ),
    "procedimento": (
        "JOIN procedimentos pr ON pr.id = e.id_procedimento",
        "pr.id::text",
        "pr.descricao",
    ),
    "prestador": (
        "JOIN prestadores p ON p.id = e.id_prestador",
        "p.id::text",
        "p.nome_ficticio",
    ),
    "regiao": (
        "JOIN regioes r ON r.id = e.id_regiao",
        "r.id::text",
        "concat(r.cidade, '/', r.uf)",
    ),
    "faixa_etaria": (
        "JOIN beneficiarios b ON b.id = e.id_beneficiario",
        "b.faixa_etaria",
        "b.faixa_etaria",
    ),
    "sexo": (
        "JOIN beneficiarios b ON b.id = e.id_beneficiario",
        "b.sexo",
        "b.sexo",
    ),
    "plano": (
        "JOIN beneficiarios b ON b.id = e.id_beneficiario "
        "JOIN planos pl ON pl.id = b.id_plano",
        "pl.id::text",
        "pl.nome",
    ),
    "contrato": (
        "JOIN beneficiarios b ON b.id = e.id_beneficiario "
        "JOIN contratos ct ON ct.id = b.id_contrato",
        "ct.id::text",
        "ct.nome",
    ),
}

# expressões de composição financeira reaproveitadas por várias INSERTs
_COMPOSICAO = """
    SUM(e.valor_pago)                                              AS despesa,
    SUM(e.valor_apresentado)                                       AS despesa_bruta,
    SUM(e.valor_glosado)                                           AS glosas,
    SUM(e.valor_coparticipacao)                                    AS coparticipacao,
    SUM(e.valor_apresentado - e.valor_glosado - e.valor_coparticipacao) AS despesa_liquida
"""


def rebuild_aggregations(session: Session, tenant_id: str = DEFAULT_TENANT) -> dict[str, int]:
    """Reconstrói todas as tabelas `agg_*` para um tenant. Retorna contagens por tabela."""
    p = {"tenant": tenant_id}
    for tbl in (
        "agg_sinistralidade_competencia", "agg_competencia_dimensao",
        "agg_prestador_competencia", "agg_beneficiario_competencia",
        "agg_contrato_competencia",
    ):
        session.execute(text(f"DELETE FROM {tbl} WHERE tenant_id = :tenant"), p)

    # ---- sinistralidade por competência ----
    session.execute(
        text(
            """
            INSERT INTO agg_sinistralidade_competencia
                (tenant_id, competencia, receita, despesa_bruta, glosas, coparticipacao,
                 despesa_liquida, sinistralidade_bruta, sinistralidade_liquida,
                 beneficiarios_ativos, exposicao_beneficiario_mes, eventos, custo_pmpm,
                 receita_media_beneficiario)
            SELECT
                CAST(:tenant AS varchar),
                c.competencia,
                COALESCE(rc.receita, 0)                                   AS receita,
                COALESCE(ev.despesa_bruta, 0)                             AS despesa_bruta,
                COALESCE(ev.glosas, 0)                                    AS glosas,
                COALESCE(ev.coparticipacao, 0)                            AS coparticipacao,
                COALESCE(ev.despesa_liquida, 0)                           AS despesa_liquida,
                CASE WHEN COALESCE(rc.receita,0) > 0
                     THEN COALESCE(ev.despesa_bruta,0) / rc.receita * 100 ELSE 0 END,
                CASE WHEN COALESCE(rc.receita,0) > 0
                     THEN COALESCE(ev.despesa_liquida,0) / rc.receita * 100 ELSE 0 END,
                COALESCE(rc.expo, 0),
                COALESCE(rc.expo, 0),
                COALESCE(ev.eventos, 0),
                CASE WHEN COALESCE(rc.expo,0) > 0
                     THEN COALESCE(ev.despesa_liquida,0) / rc.expo ELSE 0 END,
                CASE WHEN COALESCE(rc.expo,0) > 0
                     THEN COALESCE(rc.receita,0) / rc.expo ELSE 0 END
            FROM competencias c
            LEFT JOIN (
                SELECT competencia,
                       SUM(receita_contraprestacao) AS receita,
                       SUM(quantidade_beneficiarios) AS expo
                FROM receitas WHERE tenant_id = :tenant GROUP BY competencia
            ) rc ON rc.competencia = c.competencia
            LEFT JOIN (
                SELECT competencia,
                       SUM(valor_apresentado)                                       AS despesa_bruta,
                       SUM(valor_glosado)                                           AS glosas,
                       SUM(valor_coparticipacao)                                    AS coparticipacao,
                       SUM(valor_apresentado - valor_glosado - valor_coparticipacao) AS despesa_liquida,
                       COUNT(*)                                                     AS eventos
                FROM eventos_assistenciais WHERE tenant_id = :tenant GROUP BY competencia
            ) ev ON ev.competencia = c.competencia
            -- Fase 2: só a janela de dados do PRÓPRIO tenant (o calendário é global)
            WHERE c.competencia BETWEEN
                  (SELECT min(m) FROM (SELECT min(competencia) AS m FROM eventos_assistenciais WHERE tenant_id = :tenant
                                       UNION ALL SELECT min(competencia) FROM receitas WHERE tenant_id = :tenant) j)
              AND (SELECT max(m) FROM (SELECT max(competencia) AS m FROM eventos_assistenciais WHERE tenant_id = :tenant
                                       UNION ALL SELECT max(competencia) FROM receitas WHERE tenant_id = :tenant) j)
            """
        ),
        p,
    )

    # ---- dimensões (com composição financeira propagada — v1.2) ----
    for dim, (joins, chave_expr, rotulo_expr) in _DIMENSOES.items():
        session.execute(
            text(
                f"""
                INSERT INTO agg_competencia_dimensao
                    (tenant_id, competencia, dimensao, chave, rotulo,
                     despesa, despesa_bruta, glosas, coparticipacao, despesa_liquida,
                     eventos, quantidade, beneficiarios, custo_medio, freq_por_mil)
                SELECT
                    CAST(:tenant AS varchar),
                    e.competencia,
                    :dim AS dimensao,
                    {chave_expr} AS chave,
                    MIN({rotulo_expr}) AS rotulo,
                    {_COMPOSICAO},
                    COUNT(*) AS eventos,
                    SUM(e.quantidade) AS quantidade,
                    COUNT(DISTINCT e.id_beneficiario) AS beneficiarios,
                    CASE WHEN COUNT(*) > 0 THEN SUM(e.valor_pago) / COUNT(*) ELSE 0 END,
                    CASE WHEN s.exposicao_beneficiario_mes > 0
                         THEN COUNT(*)::float / s.exposicao_beneficiario_mes * 1000 ELSE 0 END
                FROM eventos_assistenciais e
                {joins}
                JOIN agg_sinistralidade_competencia s
                     ON s.competencia = e.competencia AND s.tenant_id = :tenant
                WHERE e.tenant_id = :tenant
                GROUP BY e.competencia, {chave_expr}, s.exposicao_beneficiario_mes
                """
            ),
            {"dim": dim, **p},
        )

    # ---- prestador x competência ----
    session.execute(
        text(
            """
            INSERT INTO agg_prestador_competencia
                (tenant_id, competencia, id_prestador,
                 despesa, despesa_bruta, glosas, coparticipacao, despesa_liquida,
                 eventos, beneficiarios, custo_medio, participacao,
                 procedimento_top_id, procedimento_top_share)
            WITH base AS (
                SELECT e.competencia, e.id_prestador,
                       SUM(e.valor_pago) AS despesa,
                       SUM(e.valor_apresentado) AS despesa_bruta,
                       SUM(e.valor_glosado) AS glosas,
                       SUM(e.valor_coparticipacao) AS coparticipacao,
                       SUM(e.valor_apresentado - e.valor_glosado - e.valor_coparticipacao) AS despesa_liquida,
                       COUNT(*) AS eventos,
                       COUNT(DISTINCT e.id_beneficiario) AS beneficiarios
                FROM eventos_assistenciais e
                WHERE e.tenant_id = :tenant
                GROUP BY e.competencia, e.id_prestador
            ),
            topp AS (
                SELECT competencia, id_prestador, id_procedimento, dsp,
                       ROW_NUMBER() OVER (PARTITION BY competencia, id_prestador
                                          ORDER BY dsp DESC) AS rn,
                       SUM(dsp) OVER (PARTITION BY competencia, id_prestador) AS tot
                FROM (
                    SELECT competencia, id_prestador, id_procedimento,
                           SUM(valor_pago) AS dsp
                    FROM eventos_assistenciais
                    WHERE tenant_id = :tenant
                    GROUP BY competencia, id_prestador, id_procedimento
                ) z
            ),
            mes AS (
                SELECT competencia, SUM(valor_pago) AS despesa_mes
                FROM eventos_assistenciais WHERE tenant_id = :tenant GROUP BY competencia
            )
            SELECT CAST(:tenant AS varchar), b.competencia, b.id_prestador, b.despesa, b.despesa_bruta,
                   b.glosas, b.coparticipacao, b.despesa_liquida, b.eventos, b.beneficiarios,
                   CASE WHEN b.eventos > 0 THEN b.despesa / b.eventos ELSE 0 END,
                   CASE WHEN m.despesa_mes > 0 THEN b.despesa / m.despesa_mes ELSE 0 END,
                   tp.id_procedimento,
                   CASE WHEN tp.tot > 0 THEN tp.dsp / tp.tot ELSE 0 END
            FROM base b
            JOIN mes m ON m.competencia = b.competencia
            LEFT JOIN topp tp ON tp.competencia = b.competencia
                             AND tp.id_prestador = b.id_prestador AND tp.rn = 1
            """
        ),
        p,
    )

    # ---- beneficiário x competência (com id_contrato + composição — v1.2) ----
    session.execute(
        text(
            """
            INSERT INTO agg_beneficiario_competencia
                (tenant_id, competencia, id_beneficiario, id_contrato,
                 despesa, despesa_bruta, glosas, coparticipacao, despesa_liquida, eventos)
            SELECT CAST(:tenant AS varchar), e.competencia, e.id_beneficiario, MIN(b.id_contrato),
                   SUM(e.valor_pago),
                   SUM(e.valor_apresentado),
                   SUM(e.valor_glosado),
                   SUM(e.valor_coparticipacao),
                   SUM(e.valor_apresentado - e.valor_glosado - e.valor_coparticipacao),
                   COUNT(*)
            FROM eventos_assistenciais e
            JOIN beneficiarios b ON b.id = e.id_beneficiario
            WHERE e.tenant_id = :tenant
            GROUP BY e.competencia, e.id_beneficiario
            """
        ),
        p,
    )

    # ---- contrato x competência (Contract Intelligence — v1.2) ----
    # vidas = beneficiários "ativos" do contrato no mês (aderiram até a competência e não
    # saíram até ela). despesa/eventos vêm de agg_beneficiario_competencia (já com
    # id_contrato). gini/top5_share/n_alto_custo calculados sobre despesa líquida por
    # beneficiário do contrato no mês.
    session.execute(
        text(
            """
            INSERT INTO agg_contrato_competencia
                (tenant_id, competencia, id_contrato, vidas,
                 despesa, despesa_bruta, glosas, coparticipacao, despesa_liquida,
                 eventos, beneficiarios_com_evento, custo_pmpm, gini, top5_share,
                 n_beneficiarios_alto_custo)
            WITH vidas AS (
                SELECT c.competencia, b.id_contrato, COUNT(*) AS vidas
                FROM competencias c
                JOIN beneficiarios b
                  ON b.tenant_id = :tenant
                 AND b.data_adesao <= c.competencia
                 AND (b.data_saida IS NULL OR b.data_saida > c.competencia)
                WHERE c.competencia BETWEEN
                      (SELECT min(m) FROM (SELECT min(competencia) AS m FROM eventos_assistenciais WHERE tenant_id = :tenant
                                           UNION ALL SELECT min(competencia) FROM receitas WHERE tenant_id = :tenant) j)
                  AND (SELECT max(m) FROM (SELECT max(competencia) AS m FROM eventos_assistenciais WHERE tenant_id = :tenant
                                           UNION ALL SELECT max(competencia) FROM receitas WHERE tenant_id = :tenant) j)
                GROUP BY c.competencia, b.id_contrato
            ),
            ben AS (
                SELECT ac.competencia, ac.id_contrato,
                       ac.despesa, ac.despesa_bruta, ac.glosas, ac.coparticipacao,
                       ac.despesa_liquida, ac.eventos,
                       ROW_NUMBER() OVER (PARTITION BY ac.competencia, ac.id_contrato
                                          ORDER BY ac.despesa_liquida ASC) AS rnk_asc,
                       ROW_NUMBER() OVER (PARTITION BY ac.competencia, ac.id_contrato
                                          ORDER BY ac.despesa_liquida DESC) AS rnk_desc
                FROM agg_beneficiario_competencia ac
                WHERE ac.tenant_id = :tenant AND ac.despesa_liquida > 0
            ),
            ctr AS (
                SELECT competencia, id_contrato,
                       SUM(despesa) AS despesa, SUM(despesa_bruta) AS despesa_bruta,
                       SUM(glosas) AS glosas, SUM(coparticipacao) AS coparticipacao,
                       SUM(despesa_liquida) AS despesa_liquida, SUM(eventos) AS eventos,
                       COUNT(*) AS n_ben,
                       SUM(rnk_asc * despesa_liquida) AS srv,
                       SUM(despesa_liquida) FILTER (WHERE rnk_desc <= 5) AS top5,
                       COUNT(*) FILTER (WHERE despesa_liquida >= :alto) AS n_alto
                FROM ben
                GROUP BY competencia, id_contrato
            )
            SELECT CAST(:tenant AS varchar), v.competencia, v.id_contrato, v.vidas,
                   COALESCE(ctr.despesa,0), COALESCE(ctr.despesa_bruta,0),
                   COALESCE(ctr.glosas,0), COALESCE(ctr.coparticipacao,0),
                   COALESCE(ctr.despesa_liquida,0), COALESCE(ctr.eventos,0),
                   COALESCE(ctr.n_ben,0),
                   CASE WHEN v.vidas > 0 THEN COALESCE(ctr.despesa_liquida,0) / v.vidas ELSE 0 END,
                   CASE WHEN COALESCE(ctr.n_ben,0) > 0 AND COALESCE(ctr.despesa_liquida,0) > 0
                        THEN (2.0 * ctr.srv) / (ctr.n_ben * ctr.despesa_liquida)
                             - (ctr.n_ben + 1.0) / ctr.n_ben
                        ELSE 0 END,
                   CASE WHEN COALESCE(ctr.despesa_liquida,0) > 0
                        THEN COALESCE(ctr.top5,0) / ctr.despesa_liquida ELSE 0 END,
                   COALESCE(ctr.n_alto,0)
            FROM vidas v
            LEFT JOIN ctr ON ctr.competencia = v.competencia AND ctr.id_contrato = v.id_contrato
            """
        ),
        {"alto": ALTO_CUSTO_MES, **p},
    )
    session.flush()

    return {
        "agg_sinistralidade_competencia": _count(session, tenant_id, "agg_sinistralidade_competencia"),
        "agg_competencia_dimensao": _count(session, tenant_id, "agg_competencia_dimensao"),
        "agg_prestador_competencia": _count(session, tenant_id, "agg_prestador_competencia"),
        "agg_beneficiario_competencia": _count(session, tenant_id, "agg_beneficiario_competencia"),
        "agg_contrato_competencia": _count(session, tenant_id, "agg_contrato_competencia"),
    }


def _count(session: Session, tenant_id: str, table: str) -> int:
    return int(session.execute(
        text(f"SELECT COUNT(*) FROM {table} WHERE tenant_id = :t"), {"t": tenant_id}
    ).scalar_one())


if __name__ == "__main__":  # python -m app.seed.aggregate [--tenant CODIGO]
    import argparse

    from app.db.session import AdminSessionLocal
    from app.db.tenant_scope import bind_tenant

    ap = argparse.ArgumentParser(description="Reconstrói as agg_* de um tenant")
    ap.add_argument("--tenant", default=DEFAULT_TENANT)
    tenant = ap.parse_args().tenant
    with AdminSessionLocal() as s:
        bind_tenant(s, tenant)
        print(rebuild_aggregations(s, tenant_id=tenant))
        s.commit()
