"""Faixas etárias (bandas de saúde) usadas em toda a plataforma."""

from datetime import date

# (rótulo, idade_min, idade_max_exclusivo)
FAIXAS: list[tuple[str, int, int]] = [
    ("0-1", 0, 2),
    ("2-4", 2, 5),
    ("5-9", 5, 10),
    ("10-14", 10, 15),
    ("15-19", 15, 20),
    ("20-29", 20, 30),
    ("30-39", 30, 40),
    ("40-49", 40, 50),
    ("50-59", 50, 60),
    ("60-69", 60, 70),
    ("70-79", 70, 80),
    ("80+", 80, 200),
]

FAIXA_LABELS: list[str] = [f[0] for f in FAIXAS]


def faixa_etaria(idade: int) -> str:
    """Rótulo da faixa etária para uma idade em anos."""
    for label, lo, hi in FAIXAS:
        if lo <= idade < hi:
            return label
    return FAIXAS[-1][0]


def idade_em(nascimento: date, ref: date) -> int:
    """Idade completa em anos na data de referência."""
    anos = ref.year - nascimento.year
    if (ref.month, ref.day) < (nascimento.month, nascimento.day):
        anos -= 1
    return max(anos, 0)
