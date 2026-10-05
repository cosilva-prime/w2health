"""Dependências e helpers compartilhados pelos routers de analytics.

Fundação SaaS V1: toda dependência que lê dados usa `get_tenant_db` (sessão amarrada ao
tenant do contexto autenticado). `analytics_guard(...)` monta a cadeia padrão de um módulo
analítico: permissão `analytics:read` + features exigidas — aplicada no nível do router.
"""

from __future__ import annotations

from datetime import date

from fastapi import Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.analytics.periodo import COMPARACOES, parse_competencia
from app.repositories import analytics_repo as repo
from app.saas.feature_filters import CONTRACT, DIMENSAO_FEATURE
from app.security.deps import (
    TenantContext,
    get_tenant_context,
    get_tenant_db,
    require_feature,
    require_permission,
)
from app.security.errors import ApiError
from app.security.rbac import Perm


def analytics_guard(*features: str) -> list:
    """Dependências de router: autenticado + tenant ativo + `analytics:read` + features."""
    deps = [Depends(require_permission(Perm.ANALYTICS_READ))]
    if features:
        deps.append(Depends(require_feature(*features)))
    return deps


def competencia_dep(
    competencia: str | None = Query(
        None, description="Competência AAAA-MM. Padrão: última disponível.", examples=["2026-07"]
    ),
    db: Session = Depends(get_tenant_db),
) -> date:
    disponiveis = repo.competencias(db)
    if not disponiveis:
        raise HTTPException(503, "Base analítica vazia para este ambiente.")
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


def contrato_id_dep(
    contrato_id: int | None = Query(
        None, description="v1.2 — restringe a análise a um contrato (sem receita própria)."
    ),
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_tenant_db),
) -> int | None:
    if contrato_id is None:
        return None
    if not ctx.has_feature(CONTRACT):
        raise ApiError("feature_unavailable", extra={"feature": CONTRACT})
    # contrato de outro tenant é indistinguível de inexistente
    if repo.contrato_info(db, contrato_id) is None:
        raise HTTPException(404, f"Contrato inexistente: {contrato_id}")
    return contrato_id


def exigir_feature_da_dimensao(ctx: TenantContext, dimensao: str | None) -> None:
    """Explicar por `prestador`/`contrato` expõe o módulo correspondente — exige a feature."""
    feat = DIMENSAO_FEATURE.get(dimensao or "")
    if feat is not None and not ctx.has_feature(feat):
        raise ApiError("feature_unavailable", extra={"feature": feat})
