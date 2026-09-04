"""Dependências e helpers compartilhados pelos routers de analytics."""

from __future__ import annotations

from datetime import date

from fastapi import Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.analytics.periodo import COMPARACOES, parse_competencia
from app.db.session import get_db
from app.repositories import analytics_repo as repo


def competencia_dep(
    competencia: str | None = Query(
        None, description="Competência AAAA-MM. Padrão: última disponível.", examples=["2026-07"]
    ),
    db: Session = Depends(get_db),
) -> date:
    disponiveis = repo.competencias(db)
    if not disponiveis:
        raise HTTPException(503, "Base analítica vazia — rode o seed (python -m app.seed.run).")
    if competencia is None:
        return disponiveis[-1]
    c = parse_competencia(competencia)
    if c not in disponiveis:
        raise HTTPException(404, f"Competência sem dados: {competencia}")
    return c


def comparacao_dep(
    comparacao: str = Query(
        "mes_anterior", description="Base de comparação.", examples=["mes_anterior"]
    ),
) -> str:
    if comparacao not in COMPARACOES:
        raise HTTPException(422, f"comparacao inválida. Use uma de: {', '.join(COMPARACOES)}")
    return comparacao
