"""Sinistralidade: indicador, evolução, explicação da variação e drill-down."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.analytics import cohorts, decomposition
from app.analytics import sinistralidade as sin
from app.api.v1.routes._common import comparacao_dep, competencia_dep
from app.db.session import get_db

router = APIRouter(prefix="/analytics/sinistralidade", tags=["Sinistralidade"])

_METODOS = ("bennet", "laspeyres")


def _metodo(metodo: str = Query("bennet", description="Método do bridge freq × custo.")) -> str:
    if metodo not in _METODOS:
        raise HTTPException(422, f"metodo inválido. Use: {', '.join(_METODOS)}")
    return metodo


@router.get("", summary="Indicador de sinistralidade do mês + comparação + decomposição num/den")
def indicador(
    competencia: date = Depends(competencia_dep),
    comparacao: str = Depends(comparacao_dep),
    db: Session = Depends(get_db),
) -> dict:
    return sin.indicador(db, competencia, comparacao)


@router.get("/evolucao", summary="Série mensal com sinistralidade, acumulado 12m e variações")
def evolucao(db: Session = Depends(get_db)) -> dict:
    return {"serie": sin.serie(db)}


@router.get(
    "/composicao",
    summary="Composição financeira: bruta, glosas, coparticipação, líquida + decomposição",
)
def composicao(
    competencia: date = Depends(competencia_dep),
    comparacao: str = Depends(comparacao_dep),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return sin.composicao(db, competencia, comparacao)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/explain", summary="Explicação automática: fatores da variação por dimensão + bridge")
def explain(
    competencia: date = Depends(competencia_dep),
    comparacao: str = Depends(comparacao_dep),
    dimensao: str = Query("especialidade", description="Dimensão da decomposição."),
    metodo: str = Depends(_metodo),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return decomposition.explicar(db, competencia, comparacao, dimensao, metodo)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.get(
    "/explain/{dimensao}/{chave}",
    summary="Drill-down de um fator: bridge + onde investigar (prestadores/beneficiários)",
)
def explain_drill(
    dimensao: str,
    chave: str,
    competencia: date = Depends(competencia_dep),
    comparacao: str = Depends(comparacao_dep),
    metodo: str = Depends(_metodo),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return decomposition.drill(db, competencia, dimensao, chave, comparacao, metodo)
    except KeyError as e:
        raise HTTPException(404, f"fator sem dados para {dimensao}={chave}") from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.get(
    "/explain/{dimensao}/{chave}/causas",
    summary="Por que o fator mudou? Coortes de beneficiários com FATO/HIPÓTESE/A_INVESTIGAR",
)
def explain_causas(
    dimensao: str,
    chave: str,
    competencia: date = Depends(competencia_dep),
    comparacao: str = Depends(comparacao_dep),
    db: Session = Depends(get_db),
) -> dict:
    if dimensao not in decomposition.DIMENSOES_VALIDAS:
        raise HTTPException(422, f"dimensão inválida: {dimensao}")
    return cohorts.analisar_causas(db, dimensao, chave, competencia, comparacao)
