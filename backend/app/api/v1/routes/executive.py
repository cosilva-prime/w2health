"""Visão Executiva."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.analytics import insights as insights_mod
from app.analytics import sinistralidade
from app.api.v1.routes._common import comparacao_dep, competencia_dep
from app.db.session import get_db

router = APIRouter(prefix="/executive", tags=["Visão Executiva"])


@router.get("/overview", summary="KPIs executivos + série + principais fatores de atenção")
def overview(
    competencia: date = Depends(competencia_dep),
    comparacao: str = Depends(comparacao_dep),
    db: Session = Depends(get_db),
) -> dict:
    payload = sinistralidade.executivo(db, competencia, comparacao)
    fatores = insights_mod.gerar(db, competencia, comparacao)
    payload["principais_fatores_atencao"] = fatores[:6]
    payload["meta"] = {
        "competencia": competencia.isoformat(),
        "comparacao": comparacao,
        "gerado_de": "camada analítica (agg_*)",
    }
    return payload
