"""Inteligência sobre prestadores."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.analytics import providers
from app.api.v1.routes._common import comparacao_dep, competencia_dep
from app.db.session import get_db

router = APIRouter(prefix="/analytics/prestadores", tags=["Prestadores"])


@router.get("", summary="Lista paginada de prestadores no mês")
def lista(
    competencia: date = Depends(competencia_dep),
    sort: str = Query("despesa", description="despesa|eventos|custo_medio|beneficiarios|participacao"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    return providers.lista(db, competencia, sort, page, page_size)


@router.get("/ranking-variacao", summary="Ranking de contribuição para a variação da despesa")
def ranking_variacao(
    competencia: date = Depends(competencia_dep),
    comparacao: str = Depends(comparacao_dep),
    direcao: str = Query("alta", description="alta|baixa"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> dict:
    if direcao not in ("alta", "baixa"):
        raise HTTPException(422, "direcao deve ser 'alta' ou 'baixa'")
    return providers.ranking_variacao(db, competencia, comparacao, direcao, limit)


@router.get("/anomalias", summary="Prestadores com comportamento fora do padrão (z-score vs pares)")
def anomalias(
    competencia: date = Depends(competencia_dep),
    db: Session = Depends(get_db),
) -> dict:
    return {"competencia": competencia.isoformat(), "itens": providers.anomalia_prestadores(db, competencia)}


@router.get("/{id_prestador}", summary="Detalhe do prestador: KPIs, série, procedimentos, pares")
def detalhe(
    id_prestador: int,
    competencia: date = Depends(competencia_dep),
    comparacao: str = Depends(comparacao_dep),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return providers.detalhe(db, id_prestador, competencia, comparacao)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
