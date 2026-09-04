"""Sazonalidade — distingue 'variação sazonal esperada' de 'anômala'.

Modelo simples e transparente: para cada mês do histórico calcula o esperado como
tendência (média móvel 12m até o mês) × fator sazonal do mês (média histórica daquele
mês / média geral). O resíduo padronizado (real − esperado) / desvio-padrão dos resíduos
históricos classifica o mês corrente.
"""

from __future__ import annotations

import statistics
from datetime import date


def _fatores_sazonais(hist: list[tuple[date, float]]) -> dict[int, float]:
    media_geral = statistics.fmean([v for _c, v in hist]) or 1.0
    por_mes: dict[int, list[float]] = {}
    for c, v in hist:
        por_mes.setdefault(c.month, []).append(v)
    return {
        m: (statistics.fmean(vs) / media_geral if vs else 1.0) for m, vs in por_mes.items()
    }


def _esperado(hist_ate: list[tuple[date, float]], mes: int, fatores: dict[int, float]) -> float:
    ult12 = [v for _c, v in hist_ate[-12:]] or [v for _c, v in hist_ate]
    tendencia = statistics.fmean(ult12) if ult12 else 0.0
    return tendencia * fatores.get(mes, 1.0)


def classificar(serie: list[tuple[date, float]], competencia: date, k_sigma: float = 2.0) -> dict:
    valores = {c: v for c, v in serie}
    if competencia not in valores:
        return {"classificacao": "sem_dados", "confianca": "baixa"}

    real = valores[competencia]
    historico = sorted((c, v) for c, v in serie if c < competencia)
    if len(historico) < 12:
        return {
            "classificacao": "indeterminado", "confianca": "baixa",
            "real": round(real, 2), "esperado": None,
            "motivo": "histórico insuficiente (< 12 meses) para base sazonal",
        }

    fatores = _fatores_sazonais(historico)

    # resíduos históricos (a partir do 12º mês, quando há tendência estável)
    residuos: list[float] = []
    for i in range(12, len(historico)):
        c, v = historico[i]
        esp = _esperado(historico[:i], c.month, fatores)
        residuos.append(v - esp)
    sigma = statistics.pstdev(residuos) if len(residuos) >= 3 else (statistics.pstdev(
        [v for _c, v in historico]
    ) or 1.0)
    sigma = sigma or 1.0

    esperado = _esperado(historico, competencia.month, fatores)
    desvio_padronizado = (real - esperado) / sigma
    fator_mes = fatores.get(competencia.month, 1.0)

    if abs(desvio_padronizado) <= k_sigma:
        classe = "sazonal" if abs(fator_mes - 1.0) >= 0.15 else "normal"
    else:
        classe = "anomalo"

    return {
        "classificacao": classe,
        "confianca": "media" if len(historico) >= 13 else "baixa",
        "real": round(real, 2),
        "esperado": round(esperado, 2),
        "fator_sazonal": round(fator_mes, 3),
        "desvio_padronizado": round(desvio_padronizado, 2),
        "metodologia": (
            "esperado = média_móvel_12m × fator_sazonal_do_mês; classificação por "
            "|real − esperado| / desvio-padrão dos resíduos históricos (limiar 2σ)."
        ),
    }
