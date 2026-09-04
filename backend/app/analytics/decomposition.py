"""Explicação automática da variação da sinistralidade / despesa.

`explicar` decompõe a variação por dimensão (contribuição em R$ e em % da variação) e,
para cada fator, roda o bridge frequência × custo médio. Para fatores coesos
(especialidade, grupo de despesa, procedimento) o bridge é a soma dos efeitos por
procedimento — o que separa corretamente "mais procedimentos" de "procedimento mais
caro". `drill` aprofunda um fator. Nada é estático — tudo deriva dos agregados.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.analytics import formulas as f
from app.analytics.periodo import competencia_comparacao
from app.repositories import analytics_repo as repo

DIMENSOES_VALIDAS = (
    "grupo_despesa", "tipo_atendimento", "especialidade", "procedimento",
    "prestador", "regiao", "faixa_etaria", "sexo", "plano", "contrato",
)
# Dimensões cujo bridge é montado a partir dos procedimentos que as compõem.
DIMENSOES_COESAS = {"especialidade", "grupo_despesa", "procedimento"}


def _f(x) -> float:
    return float(x) if x is not None else 0.0


def _subitens_por_chave(proc_ant: list[dict], proc_atu: list[dict], campo: str) -> dict:
    """{chave -> [(n0, p0, n1, p1), ...]} a partir do detalhe por procedimento."""
    ant: dict[str, dict[str, dict]] = {}
    atu: dict[str, dict[str, dict]] = {}
    for r in proc_ant:
        ant.setdefault(str(r[campo]), {})[r["id"]] = r
    for r in proc_atu:
        atu.setdefault(str(r[campo]), {})[r["id"]] = r
    out: dict[str, list[tuple[float, float, float, float]]] = {}
    for chave in set(ant) | set(atu):
        pares = []
        a_map, b_map = ant.get(chave, {}), atu.get(chave, {})
        for pid in set(a_map) | set(b_map):
            a, b = a_map.get(pid), b_map.get(pid)
            n0 = _f(a["eventos"]) if a else 0.0
            n1 = _f(b["eventos"]) if b else 0.0
            p0 = (_f(a["despesa"]) / n0) if n0 else 0.0
            p1 = (_f(b["despesa"]) / n1) if n1 else 0.0
            pares.append((n0, p0, n1, p1))
        out[chave] = pares
    return out


def _fator(
    chave: str, dim_ant: dict, dim_atu: dict, receita_ant: float, metodo: str,
    subitens: dict | None = None,
) -> dict:
    a = dim_ant.get(chave)
    b = dim_atu.get(chave)
    if a is None and b is None:
        raise KeyError(chave)
    rot = (b or a)["rotulo"]
    d0 = _f(a["despesa"]) if a else 0.0
    d1 = _f(b["despesa"]) if b else 0.0
    n0 = _f(a["eventos"]) if a else 0.0
    n1 = _f(b["eventos"]) if b else 0.0

    if subitens is not None and chave in subitens:
        br = f.bridge_composto(subitens[chave], n0, n1, metodo=metodo)
    else:
        p0 = (d0 / n0) if n0 else 0.0
        p1 = (d1 / n1) if n1 else 0.0
        br = f.bridge(n0, p0, n1, p1, metodo=metodo)

    impacto_pp = (d1 - d0) / receita_ant * 100.0 if receita_ant > 0 else 0.0
    return {
        "chave": chave,
        "categoria": rot,
        "despesa_anterior": round(d0, 2),
        "despesa_atual": round(d1, 2),
        "impacto_financeiro": round(d1 - d0, 2),
        "impacto_pp": round(impacto_pp, 3),
        "efeito_principal": br.efeito_principal,
        "bridge": br.as_dict(),
    }


def explicar(
    session: Session,
    competencia: date,
    comparacao: str = "mes_anterior",
    dimensao: str = "especialidade",
    metodo: str = "bennet",
    top: int = 12,
) -> dict:
    if dimensao not in DIMENSOES_VALIDAS:
        raise ValueError(f"dimensão inválida: {dimensao}")

    comp_ant = competencia_comparacao(competencia, comparacao)
    s_atu = repo.sinistralidade_mes(session, competencia)
    s_ant = repo.sinistralidade_mes(session, comp_ant)
    if s_atu is None or s_ant is None:
        raise ValueError("competência ou comparação sem dados")

    dec = f.decomposicao_sinistralidade(
        _f(s_ant["despesa"]), _f(s_ant["receita"]),
        _f(s_atu["despesa"]), _f(s_atu["receita"]),
    )

    dim_atu = repo.dimensao_mes(session, competencia, dimensao)
    dim_ant = repo.dimensao_mes(session, comp_ant, dimensao)

    subitens = None
    if dimensao in DIMENSOES_COESAS:
        campo = {"especialidade": "especialidade", "grupo_despesa": "grupo_despesa",
                 "procedimento": "id"}[dimensao]
        subitens = _subitens_por_chave(
            repo.procedimentos_mes_detalhe(session, comp_ant),
            repo.procedimentos_mes_detalhe(session, competencia),
            campo,
        )

    contribs = f.contribuicoes(
        {k: (v["rotulo"], _f(v["despesa"])) for k, v in dim_ant.items()},
        {k: (v["rotulo"], _f(v["despesa"])) for k, v in dim_atu.items()},
    )

    receita_ant = _f(s_ant["receita"])
    fatores_altos = [
        {**_fator(c.chave, dim_ant, dim_atu, receita_ant, metodo, subitens),
         "participacao_variacao": c.participacao_pct}
        for c in contribs if c.delta > 0
    ][:top]
    fatores_baixos = [
        {**_fator(c.chave, dim_ant, dim_atu, receita_ant, metodo, subitens),
         "participacao_variacao": c.participacao_pct}
        for c in contribs if c.delta < 0
    ][:top]

    return {
        "competencia": competencia.isoformat(),
        "comparacao": comparacao,
        "competencia_comparacao": comp_ant.isoformat(),
        "dimensao": dimensao,
        "metodo_bridge": metodo,
        "sinistralidade_atual": round(_f(s_atu["sinistralidade"]), 2),
        "sinistralidade_anterior": round(_f(s_ant["sinistralidade"]), 2),
        "variacao_pp": round(dec.variacao_pp, 2),
        "efeito_despesa_pp": round(dec.efeito_despesa_pp, 3),
        "efeito_receita_pp": round(dec.efeito_receita_pp, 3),
        "despesa_atual": round(_f(s_atu["despesa"]), 2),
        "despesa_anterior": round(_f(s_ant["despesa"]), 2),
        "variacao_despesa": round(_f(s_atu["despesa"]) - _f(s_ant["despesa"]), 2),
        "principais_fatores": fatores_altos,
        "fatores_reducao": fatores_baixos,
        "metodologia": (
            "Contribuição_i = D_i,1 − D_i,0; participação_i = contribuição_i / ΔD_total "
            "(ou / Σ|Δ| quando há muito cancelamento). "
            f"Bridge ({metodo}): para especialidade/grupo/procedimento, soma dos efeitos "
            "por procedimento (separa 'mais procedimentos' de 'procedimento mais caro')."
        ),
    }


def drill(
    session: Session,
    competencia: date,
    dimensao: str,
    chave: str,
    comparacao: str = "mes_anterior",
    metodo: str = "bennet",
) -> dict:
    comp_ant = competencia_comparacao(competencia, comparacao)
    s_ant = repo.sinistralidade_mes(session, comp_ant)
    dim_atu = repo.dimensao_mes(session, competencia, dimensao)
    dim_ant = repo.dimensao_mes(session, comp_ant, dimensao)
    receita_ant = _f(s_ant["receita"]) if s_ant else 0.0

    subitens = None
    if dimensao in DIMENSOES_COESAS:
        campo = {"especialidade": "especialidade", "grupo_despesa": "grupo_despesa",
                 "procedimento": "id"}[dimensao]
        subitens = _subitens_por_chave(
            repo.procedimentos_mes_detalhe(session, comp_ant),
            repo.procedimentos_mes_detalhe(session, competencia),
            campo,
        )

    fator = _fator(chave, dim_ant, dim_atu, receita_ant, metodo, subitens)
    serie = repo.dimensao_serie(session, dimensao, chave)

    onde_prestadores = repo.eventos_da_categoria(
        session, competencia, dimensao, chave, agrupar_por="prestador", limit=8
    )
    onde_beneficiarios = repo.eventos_da_categoria(
        session, competencia, dimensao, chave, agrupar_por="beneficiario", limit=8
    )
    prest_ant = {
        r["id"]: _f(r["despesa"])
        for r in repo.eventos_da_categoria(
            session, comp_ant, dimensao, chave, agrupar_por="prestador", limit=200
        )
    }
    prest_contrib = sorted(
        (
            {
                "id": r["id"], "rotulo": r["rotulo"],
                "despesa_atual": round(_f(r["despesa"]), 2),
                "despesa_anterior": round(prest_ant.get(r["id"], 0.0), 2),
                "delta": round(_f(r["despesa"]) - prest_ant.get(r["id"], 0.0), 2),
            }
            for r in repo.eventos_da_categoria(
                session, competencia, dimensao, chave, agrupar_por="prestador", limit=200
            )
        ),
        key=lambda x: abs(x["delta"]), reverse=True,
    )[:8]

    return {
        "competencia": competencia.isoformat(),
        "comparacao": comparacao,
        "dimensao": dimensao,
        "chave": chave,
        "fator": fator,
        "serie": [
            {
                "competencia": r["competencia"].isoformat(),
                "despesa": round(_f(r["despesa"]), 2),
                "eventos": r["eventos"],
                "custo_medio": round(_f(r["custo_medio"]), 2),
                "freq_por_mil": round(_f(r["freq_por_mil"]), 3),
            }
            for r in serie
        ],
        "onde_investigar": {
            "prestadores_maior_despesa": [
                {"id": r["id"], "rotulo": r["rotulo"],
                 "despesa": round(_f(r["despesa"]), 2), "eventos": r["eventos"],
                 "custo_medio": round(_f(r["custo_medio"]), 2)}
                for r in onde_prestadores
            ],
            "beneficiarios_maior_despesa": [
                {"id": r["id"], "rotulo": r["rotulo"],
                 "despesa": round(_f(r["despesa"]), 2), "eventos": r["eventos"]}
                for r in onde_beneficiarios
            ],
            "prestadores_maior_contribuicao_variacao": prest_contrib,
        },
        "metodologia": fator["bridge"],
    }
