"""Contract Intelligence (v1.2). Sem receita por contrato — ver docstring de
`app.analytics.contratos`."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.analytics import contratos as ctr
from app.api.v1.routes._common import analytics_guard, comparacao_dep, competencia_dep
from app.saas.feature_filters import filter_alertas, sanitize
from app.security.deps import TenantContext, get_tenant_context, get_tenant_db

router = APIRouter(
    prefix="/analytics/contratos", tags=["Contratos"],
    dependencies=analytics_guard("contract_intelligence"),
)


@router.get("", summary="Lista de contratos: vidas, despesa (bruta/glosa/copart/líquida), concentração")
def listar(
    competencia: date = Depends(competencia_dep),
    comparacao: str = Depends(comparacao_dep),
    db: Session = Depends(get_tenant_db),
) -> dict:
    return ctr.listar(db, competencia, comparacao)


@router.get("/{id_contrato}", summary="Detalhe do contrato: KPIs, evolução, concentração, drivers, alertas")
def detalhe(
    id_contrato: int,
    competencia: date = Depends(competencia_dep),
    comparacao: str = Depends(comparacao_dep),
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_tenant_db),
) -> dict:
    try:
        res = ctr.detalhe(db, id_contrato, competencia, comparacao)
    except ValueError as e:
        # contrato de outro tenant é indistinguível de inexistente
        raise HTTPException(404, str(e)) from e
    res = sanitize(res, ctx.features)
    if ctx.has_feature("alerts"):
        res["alertas"] = filter_alertas(res.get("alertas") or [], ctx.features)
    else:
        res["alertas"] = []
        res["restricoes_plano"] = sorted({*res.get("restricoes_plano", []), "alerts"})
    return res
