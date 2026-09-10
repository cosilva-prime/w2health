"""v1.2 — composição financeira propagada às agregações.

Identidade `despesa_liquida = despesa_bruta - glosas - coparticipacao` deve valer em
TODAS as tabelas `agg_*` (dimensão, prestador, beneficiário, contrato), não só no nível
executivo. `despesa` (Σ valor_pago) permanece = bruta − glosas.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.scenarios

_TABELAS = [
    "agg_competencia_dimensao",
    "agg_prestador_competencia",
    "agg_beneficiario_competencia",
    "agg_contrato_competencia",
]


@pytest.mark.parametrize("tabela", _TABELAS)
def test_identidade_liquida_por_tabela(db, tabela):
    linhas = db.execute(
        text(
            f"""
            SELECT
              MAX(ABS(despesa_liquida - (despesa_bruta - glosas - coparticipacao))) AS erro_liq,
              MAX(ABS(despesa - (despesa_bruta - glosas)))                           AS erro_pago,
              COUNT(*) AS n
            FROM {tabela}
            """
        )
    ).mappings().first()
    assert linhas["n"] > 0, f"{tabela} vazia"
    assert linhas["erro_liq"] < 0.5, f"{tabela}: bruta-glosas-copart != liquida ({linhas['erro_liq']})"
    assert linhas["erro_pago"] < 0.5, f"{tabela}: bruta-glosas != despesa ({linhas['erro_pago']})"


def test_soma_das_dimensoes_bate_com_executivo(db):
    """Para uma competência, a soma da despesa líquida por contrato = despesa líquida da
    carteira (todo evento pertence a exatamente um contrato)."""
    comp = "2026-09-01"
    exec_liq = db.execute(
        text("SELECT despesa_liquida FROM agg_sinistralidade_competencia WHERE competencia = :c"),
        {"c": comp},
    ).scalar_one()
    ctr_liq = db.execute(
        text("SELECT COALESCE(SUM(despesa_liquida),0) FROM agg_contrato_competencia WHERE competencia = :c"),
        {"c": comp},
    ).scalar_one()
    assert float(ctr_liq) == pytest.approx(float(exec_liq), rel=0.01)


def test_composicao_endpoint_por_dimensao(db):
    from app.analytics import sinistralidade

    ex = sinistralidade.composicao(db, __import__("datetime").date(2026, 9, 1), "mes_anterior",
                                   dimensao="especialidade")
    # sem chave -> escopo carteira (com receita)
    assert ex["decomposicao"] is not None
    # dimensão + chave conhecida -> sem receita, só composição da despesa
    from app.repositories import analytics_repo as repo
    algum = next(iter(repo.dimensao_mes(db, __import__("datetime").date(2026, 9, 1), "especialidade")))
    ex2 = sinistralidade.composicao(db, __import__("datetime").date(2026, 9, 1), "mes_anterior",
                                    dimensao="especialidade", chave=algum)
    assert ex2["decomposicao"] is None
    a = ex2["atual"]
    assert a["despesa_liquida"] == pytest.approx(
        a["despesa_bruta"] - a["glosas"] - a["coparticipacao"], abs=0.5
    )
