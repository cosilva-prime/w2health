"""Insights automáticos + concentração + catálogos + metadados."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.analytics import beneficiaries
from app.analytics import insights as insights_mod
from app.api.v1.routes._common import comparacao_dep, competencia_dep
from app.db.session import get_db
from app.repositories import analytics_repo as repo

router = APIRouter(tags=["Insights & Metadados"])


@router.get("/analytics/insights", summary="Insights automáticos derivados dos dados")
def insights(
    competencia: date = Depends(competencia_dep),
    comparacao: str = Depends(comparacao_dep),
    severidade: str | None = Query(None, description="alta|media|baixa|positiva|info"),
    tipo: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    itens = insights_mod.gerar(db, competencia, comparacao)
    if severidade:
        itens = [i for i in itens if i["severidade"] == severidade]
    if tipo:
        itens = [i for i in itens if i["tipo"] == tipo]
    return {
        "competencia": competencia.isoformat(),
        "comparacao": comparacao,
        "total": len(itens),
        "itens": itens[:limit],
    }


@router.get("/analytics/concentracao", summary="Concentração de despesa (beneficiários ou prestadores)")
def concentracao(
    competencia: date = Depends(competencia_dep),
    base: str = Query("beneficiario", description="beneficiario|prestador"),
    db: Session = Depends(get_db),
) -> dict:
    return beneficiaries.concentracao(db, competencia, base)


@router.get("/analytics/gabarito", summary="Gabarito dos cenários sintéticos plantados (QA/demo)")
def gabarito(db: Session = Depends(get_db)) -> dict:
    return {"itens": repo.gabarito(db)}


@router.get("/meta/competencias", summary="Competências disponíveis na base analítica")
def competencias(db: Session = Depends(get_db)) -> dict:
    cs = [c.isoformat() for c in repo.competencias(db)]
    return {"itens": cs, "primeira": cs[0] if cs else None, "ultima": cs[-1] if cs else None}


@router.get("/catalogos/{nome}", summary="Catálogos para filtros (planos, regioes, especialidades, ...)")
def catalogos(nome: str, db: Session = Depends(get_db)) -> dict:
    consultas = {
        "planos": "SELECT id, nome FROM planos ORDER BY nome",
        "regioes": "SELECT id, cidade || '/' || uf AS nome FROM regioes ORDER BY nome",
        "especialidades": "SELECT id, nome FROM especialidades ORDER BY nome",
        "grupos-despesa": "SELECT DISTINCT grupo_procedimento AS id, grupo_procedimento AS nome FROM procedimentos ORDER BY 1",
        "faixas-etarias": None,
        "dimensoes": None,
    }
    if nome == "faixas-etarias":
        from app.core.faixas import FAIXA_LABELS

        return {"itens": [{"id": f, "nome": f} for f in FAIXA_LABELS]}
    if nome == "dimensoes":
        from app.analytics.decomposition import DIMENSOES_VALIDAS

        return {"itens": [{"id": d, "nome": d} for d in DIMENSOES_VALIDAS]}
    sql = consultas.get(nome)
    if sql is None:
        return {"itens": []}
    rows = db.execute(text(sql)).mappings().all()
    return {"itens": [dict(r) for r in rows]}
