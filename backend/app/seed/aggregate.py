"""Job de (re)construção da camada analítica a partir da fato bruta.

Roda inteiramente no PostgreSQL (INSERT ... SELECT ... GROUP BY) — rápido mesmo com
centenas de milhares de eventos. Chamado ao final do seed e por `alembic`/CLI quando
os dados brutos mudam.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

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


def rebuild_aggregations(session: Session) -> dict[str, int]:
    """Reconstrói todas as tabelas `agg_*`. Retorna contagens por tabela."""
    session.execute(text("TRUNCATE agg_sinistralidade_competencia"))
    session.execute(text("TRUNCATE agg_competencia_dimensao RESTART IDENTITY"))
    session.execute(text("TRUNCATE agg_prestador_competencia RESTART IDENTITY"))
    session.execute(text("TRUNCATE agg_beneficiario_competencia RESTART IDENTITY"))

    # ---- sinistralidade por competência ----
    # despesa_liquida = despesa_bruta - glosas - coparticipacao (base oficial do KPI do
    # MVP — ver docs/DATA_MODEL.md). despesa_bruta = Σvalor_apresentado (nenhuma dedução).
    session.execute(
        text(
            """
            INSERT INTO agg_sinistralidade_competencia
                (competencia, receita, despesa_bruta, glosas, coparticipacao, despesa_liquida,
                 sinistralidade_bruta, sinistralidade_liquida, beneficiarios_ativos,
                 exposicao_beneficiario_mes, eventos, custo_pmpm, receita_media_beneficiario)
            SELECT
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
                FROM receitas GROUP BY competencia
            ) rc ON rc.competencia = c.competencia
            LEFT JOIN (
                SELECT competencia,
                       SUM(valor_apresentado)                                       AS despesa_bruta,
                       SUM(valor_glosado)                                           AS glosas,
                       SUM(valor_coparticipacao)                                    AS coparticipacao,
                       SUM(valor_apresentado - valor_glosado - valor_coparticipacao) AS despesa_liquida,
                       COUNT(*)                                                     AS eventos
                FROM eventos_assistenciais GROUP BY competencia
            ) ev ON ev.competencia = c.competencia
            """
        )
    )

    # ---- dimensões ----
    for dim, (joins, chave_expr, rotulo_expr) in _DIMENSOES.items():
        session.execute(
            text(
                f"""
                INSERT INTO agg_competencia_dimensao
                    (competencia, dimensao, chave, rotulo, despesa, eventos, quantidade,
                     beneficiarios, custo_medio, freq_por_mil)
                SELECT
                    e.competencia,
                    :dim AS dimensao,
                    {chave_expr} AS chave,
                    MIN({rotulo_expr}) AS rotulo,
                    SUM(e.valor_pago) AS despesa,
                    COUNT(*) AS eventos,
                    SUM(e.quantidade) AS quantidade,
                    COUNT(DISTINCT e.id_beneficiario) AS beneficiarios,
                    CASE WHEN COUNT(*) > 0 THEN SUM(e.valor_pago) / COUNT(*) ELSE 0 END,
                    CASE WHEN s.exposicao_beneficiario_mes > 0
                         THEN COUNT(*)::float / s.exposicao_beneficiario_mes * 1000 ELSE 0 END
                FROM eventos_assistenciais e
                {joins}
                JOIN agg_sinistralidade_competencia s ON s.competencia = e.competencia
                GROUP BY e.competencia, {chave_expr}, s.exposicao_beneficiario_mes
                """
            ),
            {"dim": dim},
        )

    # ---- prestador x competência ----
    session.execute(
        text(
            """
            INSERT INTO agg_prestador_competencia
                (competencia, id_prestador, despesa, eventos, beneficiarios, custo_medio,
                 participacao, procedimento_top_id, procedimento_top_share)
            WITH base AS (
                SELECT e.competencia, e.id_prestador,
                       SUM(e.valor_pago) AS despesa,
                       COUNT(*) AS eventos,
                       COUNT(DISTINCT e.id_beneficiario) AS beneficiarios
                FROM eventos_assistenciais e
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
                    GROUP BY competencia, id_prestador, id_procedimento
                ) z
            ),
            mes AS (
                SELECT competencia, SUM(valor_pago) AS despesa_mes
                FROM eventos_assistenciais GROUP BY competencia
            )
            SELECT b.competencia, b.id_prestador, b.despesa, b.eventos, b.beneficiarios,
                   CASE WHEN b.eventos > 0 THEN b.despesa / b.eventos ELSE 0 END,
                   CASE WHEN m.despesa_mes > 0 THEN b.despesa / m.despesa_mes ELSE 0 END,
                   tp.id_procedimento,
                   CASE WHEN tp.tot > 0 THEN tp.dsp / tp.tot ELSE 0 END
            FROM base b
            JOIN mes m ON m.competencia = b.competencia
            LEFT JOIN topp tp ON tp.competencia = b.competencia
                             AND tp.id_prestador = b.id_prestador AND tp.rn = 1
            """
        )
    )

    # ---- beneficiário x competência ----
    session.execute(
        text(
            """
            INSERT INTO agg_beneficiario_competencia
                (competencia, id_beneficiario, despesa, eventos)
            SELECT competencia, id_beneficiario, SUM(valor_pago), COUNT(*)
            FROM eventos_assistenciais
            GROUP BY competencia, id_beneficiario
            """
        )
    )
    session.flush()

    return {
        "agg_sinistralidade_competencia": _count(session, "agg_sinistralidade_competencia"),
        "agg_competencia_dimensao": _count(session, "agg_competencia_dimensao"),
        "agg_prestador_competencia": _count(session, "agg_prestador_competencia"),
        "agg_beneficiario_competencia": _count(session, "agg_beneficiario_competencia"),
    }


def _count(session: Session, table: str) -> int:
    return int(session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one())


if __name__ == "__main__":  # python -m app.seed.aggregate  -> só reconstrói agregações
    from app.db.session import SessionLocal

    with SessionLocal() as s:
        print(rebuild_aggregations(s))
        s.commit()
