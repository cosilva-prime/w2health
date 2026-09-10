"""Beneficiários (anonimizados) e jornada simplificada.

v1.2: `lista` aceita `?id_contrato=`; `detalhe` traz o bloco `comportamento` (recorrência,
participação na variação, eventos pontuais de alto custo); novo endpoint
`/novos-casos-alto-custo`.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.analytics import beneficiaries
from app.analytics.periodo import parse_competencia
from app.api.v1.routes._common import comparacao_dep, competencia_dep, contrato_id_dep
from app.db.session import get_db
from app.repositories import analytics_repo as repo

router = APIRouter(prefix="/analytics/beneficiarios", tags=["Beneficiários"])


def _resolve_id(db: Session, id_ou_codigo: str) -> int:
    if id_ou_codigo.upper().startswith("BEN-"):
        bid = repo.beneficiario_por_codigo(db, id_ou_codigo.upper())
    else:
        bid = int(id_ou_codigo) if id_ou_codigo.isdigit() else None
    if bid is None:
        raise HTTPException(404, "beneficiário não encontrado")
    return bid


@router.get("", summary="Lista de beneficiários por custo no período (paginada, filtrável)")
def lista(
    competencia: date = Depends(competencia_dep),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    faixa_etaria: str | None = Query(None),
    sexo: str | None = Query(None),
    id_plano: int | None = Query(None),
    id_contrato: int | None = Depends(contrato_id_dep),
    db: Session = Depends(get_db),
) -> dict:
    return beneficiaries.lista(
        db, competencia, page, page_size, faixa_etaria, sexo, id_plano, id_contrato
    )


@router.get(
    "/novos-casos-alto-custo",
    summary="C5 — beneficiários que cruzaram o limiar de despesa líquida sem histórico",
)
def novos_casos_alto_custo(
    competencia: date = Depends(competencia_dep),
    comparacao: str = Depends(comparacao_dep),
    id_contrato: int | None = Depends(contrato_id_dep),
    db: Session = Depends(get_db),
) -> dict:
    return beneficiaries.novos_casos_alto_custo(db, competencia, comparacao, contrato_id=id_contrato)


@router.get("/{id_ou_codigo}", summary="Detalhe anonimizado + evolução mensal + eventos + comportamento")
def detalhe(
    id_ou_codigo: str,
    competencia: str | None = Query(None, description="AAAA-MM — referência do bloco de comportamento."),
    db: Session = Depends(get_db),
) -> dict:
    comp = parse_competencia(competencia) if competencia else None
    try:
        return beneficiaries.detalhe(db, _resolve_id(db, id_ou_codigo), comp)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/{id_ou_codigo}/timeline", summary="Timeline assistencial simplificada")
def timeline(id_ou_codigo: str, db: Session = Depends(get_db)) -> dict:
    try:
        return beneficiaries.timeline(db, _resolve_id(db, id_ou_codigo))
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
