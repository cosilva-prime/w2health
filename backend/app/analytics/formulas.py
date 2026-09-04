"""Primitivas matemáticas do motor analítico — funções puras, sem I/O.

Toda conclusão apresentada pela plataforma nasce de uma destas funções.
"""

from __future__ import annotations

from dataclasses import dataclass

EPS = 1e-9


# ----------------------------------------------------------------------------- sinistralidade
def sinistralidade(despesa: float, receita: float) -> float:
    """Sinistralidade em % = despesa assistencial / receita assistencial * 100."""
    if receita <= 0:
        return 0.0
    return despesa / receita * 100.0


def variacao_pp(atual: float, anterior: float) -> float:
    """Variação em pontos percentuais (diferença simples de dois percentuais)."""
    return atual - anterior


def variacao_pct(atual: float, anterior: float) -> float | None:
    """Variação percentual relativa. `None` quando não há base de comparação."""
    if abs(anterior) < EPS:
        return None
    return (atual - anterior) / anterior * 100.0


def media_movel(valores: list[float], janela: int = 12) -> float | None:
    """Média móvel dos últimos `janela` valores (None se não houver dados suficientes)."""
    if len(valores) < janela:
        return None
    return sum(valores[-janela:]) / janela


def acumulado_12m(despesas: list[float], receitas: list[float]) -> float:
    """Sinistralidade acumulada dos últimos 12 meses = Σdespesa12 / Σreceita12 * 100."""
    d = sum(despesas[-12:])
    r = sum(receitas[-12:])
    return sinistralidade(d, r)


# ------------------------------------------------ decomposição numerador x denominador
@dataclass
class DecomposicaoSinistralidade:
    variacao_pp: float
    efeito_despesa_pp: float
    efeito_receita_pp: float

    def as_dict(self) -> dict:
        return {
            "variacao_pp": round(self.variacao_pp, 4),
            "efeito_despesa_pp": round(self.efeito_despesa_pp, 4),
            "efeito_receita_pp": round(self.efeito_receita_pp, 4),
        }


def decomposicao_sinistralidade(
    despesa_ant: float, receita_ant: float, despesa_atu: float, receita_atu: float
) -> DecomposicaoSinistralidade:
    """Separa a variação da sinistralidade (p.p.) em efeito-despesa e efeito-receita.

    Identidade exata:  ΔS = (ΔD / R0)  +  (D1/R1 - D1/R0)
    """
    s0 = sinistralidade(despesa_ant, receita_ant)
    s1 = sinistralidade(despesa_atu, receita_atu)
    if receita_ant <= 0 or receita_atu <= 0:
        return DecomposicaoSinistralidade(s1 - s0, s1 - s0, 0.0)
    efeito_despesa = (despesa_atu - despesa_ant) / receita_ant * 100.0
    efeito_receita = (despesa_atu / receita_atu - despesa_atu / receita_ant) * 100.0
    return DecomposicaoSinistralidade(s1 - s0, efeito_despesa, efeito_receita)


# --------------------------------------- decomposição financeira (bruta/glosa/copart/receita)
@dataclass
class DecomposicaoFinanceira:
    variacao_pp: float
    efeito_bruta_pp: float
    efeito_glosa_pp: float
    efeito_coparticipacao_pp: float
    efeito_receita_pp: float

    def as_dict(self) -> dict:
        return {
            "variacao_pp": round(self.variacao_pp, 4),
            "efeito_bruta_pp": round(self.efeito_bruta_pp, 4),
            "efeito_glosa_pp": round(self.efeito_glosa_pp, 4),
            "efeito_coparticipacao_pp": round(self.efeito_coparticipacao_pp, 4),
            "efeito_receita_pp": round(self.efeito_receita_pp, 4),
        }


def decomposicao_financeira(
    bruta0: float, glosa0: float, copart0: float, receita0: float,
    bruta1: float, glosa1: float, copart1: float, receita1: float,
) -> DecomposicaoFinanceira:
    """Decompõe a variação da sinistralidade LÍQUIDA em 4 efeitos: despesa bruta, glosa,
    coparticipação e receita.

    Identidade exata (sem termo de interação): como despesa_líquida = bruta − glosa −
    coparticipação é uma combinação LINEAR, os três efeitos de despesa somam
    exatamente ao efeito-despesa de `decomposicao_sinistralidade`, e o efeito-receita é
    idêntico ao de lá:

        efeito_bruta  =  ΔBruta / R0 · 100
        efeito_glosa  = −ΔGlosa / R0 · 100
        efeito_copart = −ΔCopart / R0 · 100
        efeito_receita = (Dliq1/R1 − Dliq1/R0) · 100
        Σ = ΔS_líquida  (exato — não apenas aproximado)
    """
    dliq0 = bruta0 - glosa0 - copart0
    dliq1 = bruta1 - glosa1 - copart1
    s0 = sinistralidade(dliq0, receita0)
    s1 = sinistralidade(dliq1, receita1)
    if receita0 <= 0 or receita1 <= 0:
        return DecomposicaoFinanceira(s1 - s0, s1 - s0, 0.0, 0.0, 0.0)
    efeito_bruta = (bruta1 - bruta0) / receita0 * 100.0
    efeito_glosa = -(glosa1 - glosa0) / receita0 * 100.0
    efeito_copart = -(copart1 - copart0) / receita0 * 100.0
    efeito_receita = (dliq1 / receita1 - dliq1 / receita0) * 100.0
    return DecomposicaoFinanceira(s1 - s0, efeito_bruta, efeito_glosa, efeito_copart, efeito_receita)


# --------------------------------------------------------- contribuição por categoria
@dataclass
class Contribuicao:
    chave: str
    rotulo: str
    valor_anterior: float
    valor_atual: float
    delta: float
    participacao_pct: float  # % da variação total explicada por esta categoria

    def as_dict(self) -> dict:
        return {
            "chave": self.chave,
            "rotulo": self.rotulo,
            "valor_anterior": round(self.valor_anterior, 2),
            "valor_atual": round(self.valor_atual, 2),
            "delta": round(self.delta, 2),
            "participacao_pct": round(self.participacao_pct, 2),
        }


def contribuicoes(
    anterior: dict[str, tuple[str, float]], atual: dict[str, tuple[str, float]]
) -> list[Contribuicao]:
    """Contribuição de cada categoria para a variação total de um agregado (ex.: despesa).

    `anterior`/`atual` mapeiam chave -> (rotulo, valor). Categorias ausentes contam como 0.
    `participacao_pct` usa a variação total como denominador; com variação total ~0,
    cai para Σ|delta| para permanecer interpretável.
    """
    chaves = set(anterior) | set(atual)
    itens: list[Contribuicao] = []
    deltas: dict[str, float] = {}
    for k in chaves:
        rot0, v0 = anterior.get(k, (None, 0.0))
        rot1, v1 = atual.get(k, (None, 0.0))
        deltas[k] = v1 - v0
        itens.append(Contribuicao(k, rot1 or rot0 or k, v0, v1, v1 - v0, 0.0))

    total = sum(deltas.values())
    soma_abs = sum(abs(d) for d in deltas.values())
    # Quando a variação líquida é pequena frente ao movimento bruto (muito cancelamento),
    # usar Σ|Δ| como denominador evita participações explosivas / sem sentido.
    if soma_abs < EPS:
        denom = 1.0
    elif abs(total) >= 0.15 * soma_abs:
        denom = total
    else:
        denom = soma_abs
    for it in itens:
        it.participacao_pct = (it.delta / denom * 100.0) if abs(denom) > EPS else 0.0

    itens.sort(key=lambda c: abs(c.delta), reverse=True)
    return itens


# --------------------------------------------------- bridge frequência x custo médio
@dataclass
class Bridge:
    delta_total: float
    efeito_frequencia: float
    efeito_custo_medio: float
    interacao: float          # 0 no método de Bennet; explícito no Laspeyres
    metodo: str
    efeito_principal: str
    qtd_anterior: float
    qtd_atual: float
    custo_medio_anterior: float
    custo_medio_atual: float

    def as_dict(self) -> dict:
        return {
            "delta_total": round(self.delta_total, 2),
            "efeito_frequencia": round(self.efeito_frequencia, 2),
            "efeito_custo_medio": round(self.efeito_custo_medio, 2),
            "interacao": round(self.interacao, 2),
            "metodo": self.metodo,
            "efeito_principal": self.efeito_principal,
            "qtd_anterior": round(self.qtd_anterior, 2),
            "qtd_atual": round(self.qtd_atual, 2),
            "custo_medio_anterior": round(self.custo_medio_anterior, 2),
            "custo_medio_atual": round(self.custo_medio_atual, 2),
            "variacao_frequencia_pct": _safe_pct(self.qtd_atual, self.qtd_anterior),
            "variacao_custo_medio_pct": _safe_pct(
                self.custo_medio_atual, self.custo_medio_anterior
            ),
        }


def _safe_pct(a: float, b: float) -> float | None:
    v = variacao_pct(a, b)
    return round(v, 2) if v is not None else None


def classificar_efeito(ef_freq: float, ef_custo: float, limiar: float = 0.65) -> str:
    """'frequencia' | 'custo_medio' | 'misto' conforme o peso relativo (|.|) de cada efeito."""
    tot = abs(ef_freq) + abs(ef_custo)
    if tot < EPS:
        return "misto"
    if abs(ef_freq) / tot >= limiar:
        return "frequencia"
    if abs(ef_custo) / tot >= limiar:
        return "custo_medio"
    return "misto"


def bennet_bridge(n0: float, p0: float, n1: float, p1: float) -> Bridge:
    """Decomposição simétrica de ΔD = n1·p1 − n0·p0 (soma exata, sem resíduo)."""
    ef_freq = (n1 - n0) * (p0 + p1) / 2.0
    ef_custo = (p1 - p0) * (n0 + n1) / 2.0
    delta = n1 * p1 - n0 * p0
    return Bridge(
        delta_total=delta, efeito_frequencia=ef_freq, efeito_custo_medio=ef_custo,
        interacao=0.0, metodo="bennet",
        efeito_principal=classificar_efeito(ef_freq, ef_custo),
        qtd_anterior=n0, qtd_atual=n1, custo_medio_anterior=p0, custo_medio_atual=p1,
    )


def laspeyres_bridge(n0: float, p0: float, n1: float, p1: float) -> Bridge:
    """Decomposição de Laspeyres: efeito freq a preço base, efeito preço a volume base,
    e o termo de interação reportado à parte."""
    ef_freq = (n1 - n0) * p0
    ef_custo = (p1 - p0) * n0
    inter = (n1 - n0) * (p1 - p0)
    delta = n1 * p1 - n0 * p0
    return Bridge(
        delta_total=delta, efeito_frequencia=ef_freq, efeito_custo_medio=ef_custo,
        interacao=inter, metodo="laspeyres",
        efeito_principal=classificar_efeito(ef_freq, ef_custo),
        qtd_anterior=n0, qtd_atual=n1, custo_medio_anterior=p0, custo_medio_atual=p1,
    )


def bridge(n0: float, p0: float, n1: float, p1: float, metodo: str = "bennet") -> Bridge:
    return laspeyres_bridge(n0, p0, n1, p1) if metodo == "laspeyres" else bennet_bridge(n0, p0, n1, p1)


def bridge_composto(
    subitens: list[tuple[float, float, float, float]],
    n0_tot: float, n1_tot: float, metodo: str = "bennet",
) -> Bridge:
    """Bridge de um fator coeso (ex.: especialidade) a partir dos sub-itens (procedimentos).

    Soma os efeitos frequência/custo de cada procedimento — separando corretamente
    'mais procedimentos' (frequência) de 'procedimento mais caro' (custo). Cada sub-item
    é (n0, p0, n1, p1).
    """
    ef_freq = ef_custo = inter = delta = 0.0
    for n0, p0, n1, p1 in subitens:
        b = bridge(n0, p0, n1, p1, metodo=metodo)
        ef_freq += b.efeito_frequencia
        ef_custo += b.efeito_custo_medio
        inter += b.interacao
        delta += b.delta_total
    p0_agg = _safe_div(sum(s[0] * s[1] for s in subitens), n0_tot)
    p1_agg = _safe_div(sum(s[2] * s[3] for s in subitens), n1_tot)
    return Bridge(
        delta_total=delta, efeito_frequencia=ef_freq, efeito_custo_medio=ef_custo,
        interacao=inter, metodo=metodo,
        efeito_principal=classificar_efeito(ef_freq, ef_custo),
        qtd_anterior=n0_tot, qtd_atual=n1_tot,
        custo_medio_anterior=p0_agg, custo_medio_atual=p1_agg,
    )


def _safe_div(a: float, b: float) -> float:
    return a / b if abs(b) > EPS else 0.0


# --------------------------------------------------------------------- concentração
@dataclass
class Concentracao:
    total: float
    n: int
    top_k_share: dict[int, float]   # k -> fração (0..1) do total nos k maiores
    pareto_k: int                   # menor k cujo share acumulado >= 0.8
    pareto_frac: float              # pareto_k / n
    gini: float

    def as_dict(self) -> dict:
        return {
            "total": round(self.total, 2),
            "n": self.n,
            "top_k_share": {k: round(v, 4) for k, v in self.top_k_share.items()},
            "pareto_k": self.pareto_k,
            "pareto_frac": round(self.pareto_frac, 4),
            "gini": round(self.gini, 4),
        }


def gini(valores: list[float]) -> float:
    """Índice de Gini (0 = igualdade perfeita, ->1 = concentração máxima)."""
    xs = sorted(v for v in valores if v is not None)
    n = len(xs)
    s = sum(xs)
    if n == 0 or s <= 0:
        return 0.0
    cum = 0.0
    for i, x in enumerate(xs, start=1):
        cum += i * x
    return (2.0 * cum) / (n * s) - (n + 1.0) / n


def concentracao(valores: list[float], ks: tuple[int, ...] = (1, 3, 5, 10, 20)) -> Concentracao:
    xs = sorted((v for v in valores if v and v > 0), reverse=True)
    n = len(xs)
    total = sum(xs)
    top_k_share = {}
    for k in ks:
        top_k_share[k] = (sum(xs[:k]) / total) if total > 0 and k <= n else (
            1.0 if total > 0 and n else 0.0
        )
    pareto_k = n
    if total > 0:
        acc = 0.0
        for i, x in enumerate(xs, start=1):
            acc += x
            if acc / total >= 0.8:
                pareto_k = i
                break
    return Concentracao(
        total=total, n=n, top_k_share=top_k_share, pareto_k=pareto_k,
        pareto_frac=(pareto_k / n) if n else 0.0, gini=gini(xs),
    )


def severidade_por_impacto(delta_pp: float) -> str:
    """Classificação de severidade de uma variação de sinistralidade (p.p.)."""
    if delta_pp >= 5.0:
        return "alta"
    if delta_pp >= 2.0:
        return "media"
    if delta_pp <= -2.0:
        return "positiva"
    return "baixa"
