"""Contract Intelligence (v1.2). Sem receita por contrato — ver docstring de
`app.analytics.contratos`."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.analytics import contratos as ctr
from app.api.v1.routes._common import comparacao_dep, competencia_dep
from app.db.session import get_db

router = APIRouter(prefix="/analytics/contratos", tags=["Contratos"])


@router.get("", summary="Lista de contratos: vidas, despesa (bruta/glosa/copart/líquida), concentração")
def listar(
    competencia: date = Depends(competencia_dep),
    comparacao: str = Depends(comparacao_dep),
    db: Session = Depends(get_db),
) -> dict:
    return ctr.listar(db, competencia, comparacao)


@router.get("/{id_contrato}", summary="Detalhe do contrato: KPIs, evolução, concentração, drivers, alertas")
def detalhe(
    id_contrato: int,
    competencia: date = Depends(competencia_dep),
    comparacao: str = Depends(comparacao_dep),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return ctr.detalhe(db, id_contrato, competencia, comparacao)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
