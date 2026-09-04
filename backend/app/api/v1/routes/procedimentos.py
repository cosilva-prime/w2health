"""Procedimentos."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.analytics import procedimentos as proc
from app.api.v1.routes._common import comparacao_dep, competencia_dep
from app.db.session import get_db

router = APIRouter(prefix="/analytics/procedimentos", tags=["Procedimentos"])


@router.get("", summary="Lista de procedimentos no mês (paginada)")
def lista(
    competencia: date = Depends(competencia_dep),
    sort: str = Query("despesa"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    return proc.lista(db, competencia, sort, page, page_size)


@router.get("/{id_procedimento}", summary="Detalhe do procedimento + série + bridge")
def detalhe(
    id_procedimento: int,
    competencia: date = Depends(competencia_dep),
    comparacao: str = Depends(comparacao_dep),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return proc.detalhe(db, id_procedimento, competencia, comparacao)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/{id_procedimento}/bridge", summary="Bridge frequência × custo médio do procedimento")
def bridge(
    id_procedimento: int,
    competencia: date = Depends(competencia_dep),
    comparacao: str = Depends(comparacao_dep),
    db: Session = Depends(get_db),
) -> dict:
    return proc.bridge(db, id_procedimento, competencia, comparacao)
