"""Visão Executiva (feature `executive_overview`).

Os "principais fatores de atenção" são insights: só aparecem com a feature `insights` e
passam pelo filtro de features (insight que leva a módulo não contratado é omitido)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.analytics import insights as insights_mod
from app.analytics import sinistralidade
from app.api.v1.routes._common import analytics_guard, comparacao_dep, competencia_dep
from app.saas.feature_filters import filter_insights
from app.security.deps import TenantContext, get_tenant_context, get_tenant_db

router = APIRouter(
    prefix="/executive", tags=["Visão Executiva"],
    dependencies=analytics_guard("executive_overview"),
)


@router.get("/overview", summary="KPIs executivos + série + principais fatores de atenção")
def overview(
    competencia: date = Depends(competencia_dep),
    comparacao: str = Depends(comparacao_dep),
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_tenant_db),
) -> dict:
    payload = sinistralidade.executivo(db, competencia, comparacao)
    if ctx.has_feature("insights"):
        fatores = filter_insights(insights_mod.gerar(db, competencia, comparacao), ctx.features)
        payload["principais_fatores_atencao"] = fatores[:6]
    else:
        payload["principais_fatores_atencao"] = []
        payload["restricoes_plano"] = ["insights"]
    payload["meta"] = {
        "competencia": competencia.isoformat(),
        "comparacao": comparacao,
        "gerado_de": "camada analítica (agg_*)",
    }
    return payload
