"""Motor de insights automáticos.

Cada insight é DERIVADO dos agregados (nunca texto fixo): se o banco muda, o insight
muda. Todo insight carrega `metricas` de suporte, `deep_link` para a tela de investigação
e `metodologia` (a fórmula que o produziu). Ordenado por `score` de relevância.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.analytics import decomposition, providers, seasonality
from app.analytics import formulas as f
from app.analytics.periodo import competencia_comparacao
from app.repositories import analytics_repo as repo

_SEV_EMOJI = {"alta": "🔴", "media": "🟠", "baixa": "🟡", "positiva": "🟢", "info": "🔵"}


def _f(x) -> float:
    return float(x) if x is not None else 0.0


def _mk(
    tipo: str, severidade: str, titulo: str, descricao: str,
    metricas: dict, deep_link: dict, score: float, metodologia: str,
) -> dict:
    return {
        "id": f"{tipo}:{deep_link.get('params', {})}",
        "tipo": tipo,
        "severidade": severidade,
        "emoji": _SEV_EMOJI.get(severidade, "🔵"),
        "titulo": titulo,
        "descricao": descricao,
        "metricas": metricas,
        "deep_link": deep_link,
        "score": round(score, 4),
        "metodologia": metodologia,
    }


def gerar(session: Session, competencia: date, comparacao: str = "mes_anterior") -> list[dict]:
    comp_ant = competencia_comparacao(competencia, comparacao)
    s_atu = repo.sinistralidade_mes(session, competencia)
    s_ant = repo.sinistralidade_mes(session, comp_ant)
    if s_atu is None or s_ant is None:
        return []

    insights: list[dict] = []
    dec = f.decomposicao_sinistralidade(
        _f(s_ant["despesa"]), _f(s_ant["receita"]), _f(s_atu["despesa"]), _f(s_atu["receita"])
    )
    var_pp = dec.variacao_pp
    sev = f.severidade_por_impacto(var_pp)

    # 1) Variação da sinistralidade -----------------------------------------------------
    direcao = "aumentou" if var_pp >= 0 else "reduziu"
    insights.append(_mk(
        "variacao_sinistralidade", sev,
        f"A sinistralidade {direcao} {abs(var_pp):.1f} p.p.",
        f"De {_f(s_ant['sinistralidade']):.1f}% para {_f(s_atu['sinistralidade']):.1f}% "
        f"({comparacao.replace('_', ' ')}).",
        {
            "sinistralidade_atual": round(_f(s_atu["sinistralidade"]), 2),
            "sinistralidade_anterior": round(_f(s_ant["sinistralidade"]), 2),
            "variacao_pp": round(var_pp, 2),
            "efeito_despesa_pp": round(dec.efeito_despesa_pp, 2),
            "efeito_receita_pp": round(dec.efeito_receita_pp, 2),
        },
        {"rota": "/sinistralidade", "params": {"competencia": competencia.isoformat(),
                                               "comparacao": comparacao}},
        score=abs(var_pp) * 2.0,
        metodologia="ΔS (p.p.) = S1 − S0; efeitos por decomposição num/den.",
    ))

    # 2) Efeito da receita (denominador) ----------------------------------------------
    if abs(dec.efeito_receita_pp) >= 1.0 and abs(dec.efeito_receita_pp) >= 0.35 * abs(var_pp or 1):
        pos = dec.efeito_receita_pp > 0
        insights.append(_mk(
            "efeito_receita", "media" if pos else "positiva",
            f"O comportamento da receita {'elevou' if pos else 'reduziu'} a sinistralidade em "
            f"{abs(dec.efeito_receita_pp):.1f} p.p.",
            "Parte da variação veio do denominador (contraprestações), não da despesa "
            "assistencial.",
            {"efeito_receita_pp": round(dec.efeito_receita_pp, 2),
             "efeito_despesa_pp": round(dec.efeito_despesa_pp, 2),
             "receita_atual": round(_f(s_atu["receita"]), 2),
             "receita_anterior": round(_f(s_ant["receita"]), 2)},
            {"rota": "/sinistralidade", "params": {"competencia": competencia.isoformat()}},
            score=abs(dec.efeito_receita_pp) * 1.5,
            metodologia="efeito_receita = D1/R1 − D1/R0 (em p.p.).",
        ))

    # 3) Fator dominante por especialidade + bridge ----------------------------------
    exp_esp = decomposition.explicar(session, competencia, comparacao, "especialidade")
    todos_esp = exp_esp["principais_fatores"] + exp_esp["fatores_reducao"]
    if todos_esp:
        top = max(todos_esp, key=lambda x: abs(x["impacto_pp"]))
        br = top["bridge"]
        sobe = top["impacto_financeiro"] >= 0
        verbo = "pressionou" if sobe else "aliviou"
        efeito_txt = {
            "frequencia": "predominantemente por frequência",
            "custo_medio": "predominantemente por custo médio",
            "misto": "por combinação de frequência e custo médio",
        }[top["efeito_principal"]]
        insights.append(_mk(
            "fator_dominante_especialidade",
            ("alta" if abs(top["impacto_pp"]) >= 2 else "media") if sobe else "positiva",
            f"{top['categoria']} {verbo} a despesa em R$ {abs(top['impacto_financeiro']):,.0f} "
            f"({abs(top['participacao_variacao']):.0f}% da variação)".replace(",", "."),
            f"{top['impacto_pp']:+.1f} p.p. de sinistralidade. Movimento {efeito_txt} "
            f"(frequência {br['variacao_frequencia_pct']}%, custo médio "
            f"{br['variacao_custo_medio_pct']}%).",
            {
                "participacao_variacao": top["participacao_variacao"],
                "impacto_financeiro": top["impacto_financeiro"],
                "impacto_pp": top["impacto_pp"],
                "efeito_principal": top["efeito_principal"],
                "efeito_frequencia": br["efeito_frequencia"],
                "efeito_custo_medio": br["efeito_custo_medio"],
            },
            {"rota": "/sinistralidade", "params": {
                "competencia": competencia.isoformat(), "comparacao": comparacao,
                "dimensao": "especialidade", "chave": top["chave"]}},
            score=abs(top["impacto_pp"]) * 2.2 + abs(top["participacao_variacao"]) * 0.02,
            metodologia="fator com maior |impacto em p.p.|; bridge de Bennet (soma dos efeitos por procedimento).",
        ))

    # 4) Fator dominante por grupo de despesa --------------------------------------
    exp_grp = decomposition.explicar(session, competencia, comparacao, "grupo_despesa")
    todos_grp = exp_grp["principais_fatores"] + exp_grp["fatores_reducao"]
    if todos_grp:
        top = max(todos_grp, key=lambda x: abs(x["impacto_pp"]))
        insights.append(_mk(
            "fator_dominante_grupo", "media" if top["impacto_financeiro"] >= 0 else "positiva",
            f"O grupo '{top['categoria']}' liderou a variação da despesa",
            f"Contribuição de R$ {top['impacto_financeiro']:,.0f} "
            f"({abs(top['participacao_variacao']):.0f}% da variação); efeito "
            f"{top['efeito_principal']}.".replace(",", "."),
            {"participacao_variacao": top["participacao_variacao"],
             "impacto_financeiro": top["impacto_financeiro"],
             "efeito_principal": top["efeito_principal"]},
            {"rota": "/sinistralidade", "params": {
                "competencia": competencia.isoformat(), "dimensao": "grupo_despesa",
                "chave": top["chave"]}},
            score=abs(top["impacto_pp"]) * 1.6,
            metodologia="fator do grupo com maior |impacto p.p.|.",
        ))

    # 5) Internações MoM -----------------------------------------------------------
    exp_tipo = decomposition.explicar(session, competencia, comparacao, "tipo_atendimento")
    intern = next(
        (x for x in exp_tipo["principais_fatores"] + exp_tipo["fatores_reducao"]
         if x["chave"] == "internacao"), None,
    )
    if intern:
        vf = intern["bridge"]["variacao_frequencia_pct"]
        if vf is not None and abs(vf) >= 8:
            insights.append(_mk(
                "internacoes", "alta" if vf >= 15 else "media",
                f"Internações {'aumentaram' if vf > 0 else 'reduziram'} {abs(vf):.0f}% "
                f"em relação à comparação",
                f"Impacto de R$ {intern['impacto_financeiro']:,.0f}; efeito principal: "
                f"{intern['efeito_principal']}.".replace(",", "."),
                {"variacao_frequencia_pct": vf,
                 "impacto_financeiro": intern["impacto_financeiro"],
                 "efeito_principal": intern["efeito_principal"]},
                {"rota": "/sinistralidade", "params": {
                    "competencia": competencia.isoformat(), "dimensao": "tipo_atendimento",
                    "chave": "internacao"}},
                score=abs(vf) * 0.12 + abs(intern["impacto_pp"]) * 1.5,
                metodologia="Δfrequência de internações; bridge de Bennet.",
            ))

    # 6) Concentração da variação em prestadores ---------------------------------
    rk = providers.ranking_variacao(session, competencia, comparacao, "alta", limit=3)
    if rk["itens"]:
        top3 = sum(x["impacto"] for x in rk["itens"])
        total_alta = sum(
            max(0.0, _f(a.get("despesa", 0)) - _f(b.get("despesa", 0)))
            for a, b in _pairs_prest(session, competencia, comp_ant)
        )
        share = (top3 / total_alta) if total_alta > 0 else 0.0
        if share >= 0.25:
            nomes = ", ".join(x["nome"] for x in rk["itens"])
            insights.append(_mk(
                "concentracao_prestadores", "alta" if share >= 0.5 else "media",
                f"3 prestadores concentraram {share * 100:.0f}% do aumento de custos",
                f"{nomes}. Impacto somado de R$ {top3:,.0f}.".replace(",", "."),
                {"share_top3": round(share, 3), "impacto_top3": round(top3, 2),
                 "prestadores": [{"id": x["id_prestador"], "nome": x["nome"],
                                  "impacto": x["impacto"]} for x in rk["itens"]]},
                {"rota": "/prestadores", "params": {"competencia": competencia.isoformat(),
                                                    "comparacao": comparacao}},
                score=share * 8.0,
                metodologia="Σ(Δdespesa dos 3 maiores) / Σ(Δdespesa positiva de todos).",
            ))

    # 7) Prestador fora do padrão ---------------------------------------------------
    anomalias = providers.anomalia_prestadores(session, competencia)
    if anomalias:
        a = anomalias[0]
        insights.append(_mk(
            "prestador_anomalo", a["severidade"],
            f"{a['nome']} apresenta comportamento fora do padrão",
            f"Custo médio de R$ {a['custo_medio']:,.0f} e desvios relevantes vs pares de "
            f"{a['especialidade_principal']} ({', '.join(a['metricas_fora_padrao'])}).".replace(",", "."),
            {"zscores": a["zscores"], "metricas_fora_padrao": a["metricas_fora_padrao"],
             "custo_medio": a["custo_medio"], "despesa": a["despesa"]},
            {"rota": f"/prestadores/{a['id_prestador']}",
             "params": {"competencia": competencia.isoformat()}},
            score=5.0 + max(abs(v) for v in a["zscores"].values()),
            metodologia="z-score vs pares da mesma especialidade principal.",
        ))

    # 8) Concentração de despesa em beneficiários ------------------------------
    valores = repo.despesa_por_beneficiario(session, competencia)
    if valores:
        c = f.concentracao(valores, ks=(1, 5))
        n = c.n
        k5 = max(1, round(n * 0.05))
        share5 = sum(sorted(valores, reverse=True)[:k5]) / c.total if c.total else 0.0
        insights.append(_mk(
            "concentracao_beneficiarios", "media" if share5 >= 0.35 else "info",
            f"5% dos beneficiários concentraram {share5 * 100:.0f}% da despesa do período",
            f"Índice de Gini {c.gini:.2f}; ponto de Pareto em "
            f"{c.pareto_frac * 100:.0f}% dos beneficiários.",
            {"share_top5pct": round(share5, 3), "gini": c.gini,
             "pareto_frac": c.pareto_frac, "n_beneficiarios": n},
            {"rota": "/beneficiarios", "params": {"competencia": competencia.isoformat()}},
            score=share5 * 5.0,
            metodologia="share dos 5% maiores; Gini sobre despesa por beneficiário.",
        ))

    # 9) Melhora / redução (maior fator negativo) -------------------------------
    reducoes = exp_esp["fatores_reducao"] + exp_grp["fatores_reducao"]
    reducoes = [r for r in reducoes if r["impacto_financeiro"] < 0]
    if reducoes:
        r = min(reducoes, key=lambda x: x["impacto_financeiro"])
        insights.append(_mk(
            "reducao_despesa", "positiva",
            f"{r['categoria']} reduziu a despesa em R$ {abs(r['impacto_financeiro']):,.0f}".replace(",", "."),
            f"Alívio de {abs(r['impacto_pp']):.1f} p.p. na sinistralidade; efeito principal: "
            f"{r['efeito_principal']}.",
            {"impacto_financeiro": r["impacto_financeiro"], "impacto_pp": r["impacto_pp"],
             "efeito_principal": r["efeito_principal"]},
            {"rota": "/sinistralidade", "params": {
                "competencia": competencia.isoformat(), "dimensao": r.get("dimensao", "especialidade"),
                "chave": r["chave"]}},
            score=abs(r["impacto_pp"]) * 1.8,
            metodologia="maior contribuição negativa para ΔD; bridge de Bennet.",
        ))

    # 10) Sazonalidade respiratória ------------------------------------------
    pneumo = _serie_dim_evt(session, "especialidade", _chave_pneumologia(session))
    if pneumo:
        cls = seasonality.classificar(pneumo, competencia)
        if cls["classificacao"] in ("sazonal", "anomalo"):
            insights.append(_mk(
                "sazonalidade", "info" if cls["classificacao"] == "sazonal" else "media",
                f"Atendimentos de pneumologia: variação {cls['classificacao']}",
                f"Real {cls['real']:.0f} vs esperado {cls['esperado']:.0f} "
                f"(fator sazonal {cls.get('fator_sazonal')}).",
                cls,
                {"rota": "/sinistralidade", "params": {
                    "competencia": competencia.isoformat(), "dimensao": "especialidade",
                    "chave": _chave_pneumologia(session)}},
                score=1.5 if cls["classificacao"] == "sazonal" else 3.0,
                metodologia=cls["metodologia"],
            ))

    insights.sort(key=lambda x: x["score"], reverse=True)
    return insights


# --------------------------------------------------------------------------- helpers
def _pairs_prest(session: Session, comp: date, comp_ant: date):
    atu = {r["id_prestador"]: r for r in repo.prestadores_mes(session, comp)}
    ant = {r["id_prestador"]: r for r in repo.prestadores_mes(session, comp_ant)}
    return [(atu.get(p, {}), ant.get(p, {})) for p in set(atu) | set(ant)]


def _serie_dim_evt(session: Session, dimensao: str, chave: str | None):
    if not chave:
        return []
    return [(r["competencia"], float(r["eventos"])) for r in repo.dimensao_serie(session, dimensao, chave)]


def _chave_pneumologia(session: Session) -> str | None:
    from sqlalchemy import text
    r = session.execute(
        text("SELECT id::text FROM especialidades WHERE codigo = 'PNEUMOLOGIA'")
    ).scalar_one_or_none()
    return r
