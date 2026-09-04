"""Utilitários de competência/comparação."""

from __future__ import annotations

from datetime import date

COMPARACOES = ("mes_anterior", "ano_anterior", "acumulado_12m")


def mes_anterior(c: date) -> date:
    return date(c.year - 1, 12, 1) if c.month == 1 else date(c.year, c.month - 1, 1)


def mesmo_mes_ano_anterior(c: date) -> date:
    return date(c.year - 1, c.month, 1)


def competencia_comparacao(c: date, comparacao: str) -> date:
    if comparacao == "ano_anterior":
        return mesmo_mes_ano_anterior(c)
    return mes_anterior(c)


def parse_competencia(valor: str | date) -> date:
    if isinstance(valor, date):
        return date(valor.year, valor.month, 1)
    ano, mes = valor.split("-")[:2]
    return date(int(ano), int(mes), 1)
