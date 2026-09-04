"""Catálogo FECHADO de indicadores para regras de alerta (v1.1, Etapa C).

Decisão de escopo deliberada: em vez de uma linguagem de expressões livre (risco de
segurança/complexidade), cada indicador é uma função explícita no código, reaproveitando
o motor analítico já existente. A genericidade pedida vem da combinatória
`entidade × indicador × operador × limite`, não de fórmulas arbitrárias.

Cada função recebe (session, competencia, comparacao, escopo) e devolve uma lista de
`{entidade_id, rotulo, valor}` — um valor por instância da entidade no período.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.analytics import decomposition, providers, sinistralidade
from app.analytics.periodo import competencia_comparacao
from app.repositories import analytics_repo as repo

Funcao = Callable[[Session, date, str, dict], list[dict]]


@dataclass(frozen=True)
class DefinicaoIndicador:
    chave: str
    entidade: str
    rotulo: str
    unidade: str  # '%' | 'R$' | 'un' | 'z'
    descricao: str
    funcao: Funcao


def _pct(a: float, b: float) -> float:
    return (a - b) / b * 100.0 if abs(b) > 1e-9 else 0.0


# --------------------------------------------------------------------------- BENEFICIÁRIO
def _ben_participacao_despesa(session, competencia, comparacao, escopo):
    dados = repo.beneficiarios_despesa_mes(session, competencia)
    total = sum(v["despesa"] for v in dados.values()) or 1.0
    return [
        {"entidade_id": i, "rotulo": v["codigo"], "valor": v["despesa"] / total * 100}
        for i, v in dados.items()
    ]


def _ben_participacao_variacao(session, competencia, comparacao, escopo):
    comp_ant = competencia_comparacao(competencia, comparacao)
    atu = repo.beneficiarios_despesa_mes(session, competencia)
    ant = repo.beneficiarios_despesa_mes(session, comp_ant)
    delta_total = sum(v["despesa"] for v in atu.values()) - sum(v["despesa"] for v in ant.values())
    soma_abs = sum(
        abs(atu.get(i, {}).get("despesa", 0.0) - ant.get(i, {}).get("despesa", 0.0))
        for i in set(atu) | set(ant)
    ) or 1.0
    denom = delta_total if abs(delta_total) >= 0.15 * soma_abs else soma_abs
    if abs(denom) < 1e-9:
        return []
    out = []
    for i in set(atu) | set(ant):
        d = atu.get(i, {}).get("despesa", 0.0) - ant.get(i, {}).get("despesa", 0.0)
        cod = (atu.get(i) or ant.get(i))["codigo"]
        out.append({"entidade_id": i, "rotulo": cod, "valor": abs(d / denom * 100)})
    return out


def _ben_custo_mensal(session, competencia, comparacao, escopo):
    dados = repo.beneficiarios_despesa_mes(session, competencia)
    return [{"entidade_id": i, "rotulo": v["codigo"], "valor": v["despesa"]} for i, v in dados.items()]


def _ben_crescimento_percentual(session, competencia, comparacao, escopo):
    comp_ant = competencia_comparacao(competencia, comparacao)
    atu = repo.beneficiarios_despesa_mes(session, competencia)
    ant = repo.beneficiarios_despesa_mes(session, comp_ant)
    out = []
    for i, v in atu.items():
        anterior = ant.get(i, {}).get("despesa", 0.0)
        if anterior > 0:
            out.append({"entidade_id": i, "rotulo": v["codigo"], "valor": _pct(v["despesa"], anterior)})
    return out


def _ben_quantidade_eventos(session, competencia, comparacao, escopo):
    dados = repo.beneficiarios_despesa_mes(session, competencia)
    return [{"entidade_id": i, "rotulo": v["codigo"], "valor": float(v["eventos"])} for i, v in dados.items()]


# ----------------------------------------------------------------------------- PRESTADOR
def _prest_participacao_despesa(session, competencia, comparacao, escopo):
    rows = repo.prestadores_mes(session, competencia)
    return [{"entidade_id": r["id_prestador"], "rotulo": r["nome"], "valor": r["participacao"] * 100} for r in rows]


def _prest_crescimento_despesa(session, competencia, comparacao, escopo):
    rk = providers.ranking_variacao(session, competencia, comparacao, "alta", limit=10_000)
    return [
        {"entidade_id": r["id_prestador"], "rotulo": r["nome"],
         "valor": _pct(r["despesa_atual"], r["despesa_anterior"])}
        for r in rk["itens"] if r["despesa_anterior"] > 0
    ]


def _prest_crescimento_frequencia(session, competencia, comparacao, escopo):
    comp_ant = competencia_comparacao(competencia, comparacao)
    atu = {r["id_prestador"]: r for r in repo.prestadores_mes(session, competencia)}
    ant = {r["id_prestador"]: r for r in repo.prestadores_mes(session, comp_ant)}
    out = []
    for pid, r in atu.items():
        a = ant.get(pid)
        if a and a["eventos"] > 0:
            out.append({"entidade_id": pid, "rotulo": r["nome"], "valor": _pct(r["eventos"], a["eventos"])})
    return out


def _prest_custo_medio_vs_pares(session, competencia, comparacao, escopo):
    achados = providers.anomalia_prestadores(session, competencia)
    return [
        {"entidade_id": a["id_prestador"], "rotulo": a["nome"], "valor": abs(a["zscores"].get("custo_medio", 0.0))}
        for a in achados
    ]


def _prest_concentracao(session, competencia, comparacao, escopo):
    rows = repo.prestadores_mes(session, competencia)
    return [
        {"entidade_id": r["id_prestador"], "rotulo": r["nome"], "valor": r["procedimento_top_share"] * 100}
        for r in rows
    ]


# --------------------------------------------------------------------------- PROCEDIMENTO
def _proc_indicador_bridge(campo: str) -> Funcao:
    def f(session, competencia, comparacao, escopo):
        ex = decomposition.explicar(session, competencia, comparacao, "procedimento", top=10_000)
        fatores = ex["principais_fatores"] + ex["fatores_reducao"]
        out = []
        for ft in fatores:
            valor = ft["bridge"].get(campo) if campo in ("variacao_frequencia_pct", "variacao_custo_medio_pct") else ft.get(campo)
            if valor is None:
                continue
            out.append({"entidade_id": ft["chave"], "rotulo": ft["categoria"], "valor": abs(valor)})
        return out
    return f


# --------------------------------------------------------------------------------- PLANO
def _plano_sinistralidade(session, competencia, comparacao, escopo):
    rows = repo.planos_sinistralidade_mes(session, competencia)
    return [{"entidade_id": r["id"], "rotulo": r["rotulo"], "valor": r["sinistralidade"]} for r in rows]


def _plano_variacao_pp(session, competencia, comparacao, escopo):
    comp_ant = competencia_comparacao(competencia, comparacao)
    atu = {r["id"]: r for r in repo.planos_sinistralidade_mes(session, competencia)}
    ant = {r["id"]: r for r in repo.planos_sinistralidade_mes(session, comp_ant)}
    out = []
    for pid, r in atu.items():
        a = ant.get(pid)
        if a:
            out.append({"entidade_id": pid, "rotulo": r["rotulo"], "valor": abs(r["sinistralidade"] - a["sinistralidade"])})
    return out


def _plano_quantidade_vidas(session, competencia, comparacao, escopo):
    rows = repo.planos_sinistralidade_mes(session, competencia)
    return [{"entidade_id": r["id"], "rotulo": r["rotulo"], "valor": float(r["vidas"])} for r in rows]


# ------------------------------------------------------------------------------- CONTRATO
def _contrato_despesa(session, competencia, comparacao, escopo):
    dim = repo.dimensao_mes(session, competencia, "contrato")
    return [{"entidade_id": k, "rotulo": v["rotulo"], "valor": v["despesa"]} for k, v in dim.items()]


def _contrato_participacao_variacao(session, competencia, comparacao, escopo):
    ex = decomposition.explicar(session, competencia, comparacao, "contrato", top=10_000)
    fatores = ex["principais_fatores"] + ex["fatores_reducao"]
    return [{"entidade_id": ft["chave"], "rotulo": ft["categoria"], "valor": abs(ft["participacao_variacao"])} for ft in fatores]


def _contrato_quantidade_vidas(session, competencia, comparacao, escopo):
    vidas = repo.contratos_vidas_mes(session)
    return [{"entidade_id": i, "rotulo": v["rotulo"], "valor": float(v["vidas"])} for i, v in vidas.items()]


# ------------------------------------------------------------------------------ FINANCEIRO
def _fin_variacao(campo_atual: str, campo_ref_pct: bool = False) -> Funcao:
    def f(session, competencia, comparacao, escopo):
        c = sinistralidade.composicao(session, competencia, comparacao)
        if not c.get("comparacao_valores"):
            return []
        atu, ant = c["atual"][campo_atual], c["comparacao_valores"][campo_atual]
        valor = abs(_pct(atu, ant)) if campo_ref_pct else abs(atu - ant)
        return [{"entidade_id": "periodo", "rotulo": f"{competencia.isoformat()[:7]}", "valor": valor}]
    return f


#  Chave = (entidade, indicador) — o mesmo nome de indicador (ex.: "participacao_variacao")
#  existe para várias entidades, então a chave precisa incluir a entidade.
CATALOGO: dict[tuple[str, str], DefinicaoIndicador] = {}


def _reg(chave: str, entidade: str, rotulo: str, unidade: str, descricao: str, funcao: Funcao) -> None:
    CATALOGO[(entidade, chave)] = DefinicaoIndicador(chave, entidade, rotulo, unidade, descricao, funcao)


def obter(entidade: str, chave: str) -> DefinicaoIndicador | None:
    return CATALOGO.get((entidade, chave))


_reg("participacao_despesa", "beneficiario", "Participação na despesa", "%",
     "Despesa do beneficiário / despesa total do mês.", _ben_participacao_despesa)
_reg("participacao_variacao", "beneficiario", "Participação na variação da sinistralidade", "%",
     "Δdespesa do beneficiário / Δdespesa total do período.", _ben_participacao_variacao)
_reg("custo_mensal", "beneficiario", "Custo mensal", "R$", "Despesa do beneficiário no mês.", _ben_custo_mensal)
_reg("crescimento_percentual", "beneficiario", "Crescimento percentual", "%",
     "Variação % da despesa do beneficiário vs período de comparação.", _ben_crescimento_percentual)
_reg("quantidade_eventos", "beneficiario", "Quantidade de eventos", "un",
     "Número de eventos assistenciais do beneficiário no mês.", _ben_quantidade_eventos)

_reg("participacao_despesa", "prestador", "Participação na despesa", "%",
     "Despesa do prestador / despesa total do mês.", _prest_participacao_despesa)
_reg("crescimento_despesa", "prestador", "Crescimento da despesa", "%",
     "Variação % da despesa do prestador vs período de comparação.", _prest_crescimento_despesa)
_reg("crescimento_frequencia", "prestador", "Crescimento da frequência", "%",
     "Variação % de eventos do prestador vs período de comparação.", _prest_crescimento_frequencia)
_reg("custo_medio_vs_pares", "prestador", "Custo médio vs pares (z-score)", "z",
     "Desvio-padrão do custo médio do prestador vs pares da mesma especialidade.", _prest_custo_medio_vs_pares)
_reg("concentracao", "prestador", "Concentração em 1 procedimento", "%",
     "Participação do procedimento mais frequente na despesa do prestador.", _prest_concentracao)

_reg("crescimento_frequencia", "procedimento", "Crescimento da frequência", "%",
     "Variação % de frequência do procedimento.", _proc_indicador_bridge("variacao_frequencia_pct"))
_reg("crescimento_custo_medio", "procedimento", "Crescimento do custo médio", "%",
     "Variação % do custo médio do procedimento.", _proc_indicador_bridge("variacao_custo_medio_pct"))
_reg("impacto_financeiro", "procedimento", "Impacto financeiro", "R$",
     "Δdespesa do procedimento no período.", _proc_indicador_bridge("impacto_financeiro"))
_reg("participacao_variacao", "procedimento", "Participação na variação", "%",
     "Participação do procedimento na variação total da despesa.", _proc_indicador_bridge("participacao_variacao"))

_reg("sinistralidade", "plano", "Sinistralidade", "%", "Despesa/receita do plano no mês.", _plano_sinistralidade)
_reg("variacao_pp", "plano", "Variação em p.p.", "p.p.",
     "Variação da sinistralidade do plano vs período de comparação.", _plano_variacao_pp)
_reg("quantidade_vidas", "plano", "Quantidade de vidas", "un", "Beneficiários ativos no plano.", _plano_quantidade_vidas)

_reg("despesa", "contrato", "Despesa", "R$", "Despesa assistencial do contrato no mês.", _contrato_despesa)
_reg("participacao_variacao", "contrato", "Participação na variação", "%",
     "Participação do contrato na variação total da despesa (sem receita própria — "
     "sinistralidade por contrato depende do módulo de reajuste, fora do escopo da v1.1).",
     _contrato_participacao_variacao)
_reg("quantidade_vidas", "contrato", "Quantidade de vidas", "un", "Beneficiários ativos no contrato.",
     _contrato_quantidade_vidas)

_reg("variacao_glosa_pct", "financeiro", "Variação da glosa", "%",
     "Variação % da glosa total do período.", _fin_variacao("glosas", campo_ref_pct=True))
_reg("variacao_coparticipacao_pct", "financeiro", "Variação da coparticipação", "%",
     "Variação % da coparticipação total do período.", _fin_variacao("coparticipacao", campo_ref_pct=True))
_reg("impacto_glosa", "financeiro", "Impacto financeiro da glosa", "R$",
     "Δglosa em R$ no período.", _fin_variacao("glosas"))
_reg("impacto_coparticipacao", "financeiro", "Impacto financeiro da coparticipação", "R$",
     "Δcoparticipação em R$ no período.", _fin_variacao("coparticipacao"))


def catalogo_por_entidade() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for d in CATALOGO.values():
        out.setdefault(d.entidade, []).append(
            {"chave": d.chave, "rotulo": d.rotulo, "unidade": d.unidade, "descricao": d.descricao}
        )
    return out
