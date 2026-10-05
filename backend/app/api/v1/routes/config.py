"""Configuração de regras de alerta (v1.1, Etapa C).

Fundação SaaS V1 — a dívida técnica "escrita sem autenticação" foi resolvida:
* leitura: `alert_rules:read` (VIEWER+) · escrita: `alert_rules:write` (MANAGER+);
* feature `alerts` obrigatória; regras sempre do tenant do contexto (`config_repo`);
* toda criação/alteração/exclusão é auditada na mesma transação;
* limite contratual `limits.max_alert_rules` respeitado.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.analytics import alerts, indicadores
from app.api.v1.routes._common import analytics_guard, comparacao_dep, competencia_dep
from app.repositories import config_repo
from app.saas import audit, settings_catalog
from app.saas.feature_filters import filter_alertas
from app.schemas.alertas import RegraAlertaCreate, RegraAlertaOut, RegraAlertaUpdate
from app.security.deps import (
    TenantContext,
    get_tenant_context,
    get_tenant_db,
    require_feature,
    require_permission,
)
from app.security.errors import ApiError
from app.security.rbac import Perm

router = APIRouter(tags=["Configuração"], dependencies=analytics_guard("alerts"))

_LER = require_permission(Perm.ALERT_RULES_READ)
_ESCREVER = require_permission(Perm.ALERT_RULES_WRITE)


@router.get("/config/indicadores", summary="Catálogo fechado de indicadores para regras de alerta")
def catalogo_indicadores() -> dict:
    return {"itens": indicadores.catalogo_por_entidade()}


@router.get("/config/regras-alerta", response_model=list[RegraAlertaOut], summary="Lista regras de alerta")
def listar_regras(_ctx: TenantContext = Depends(_LER), db: Session = Depends(get_tenant_db)) -> list[RegraAlertaOut]:
    return [RegraAlertaOut.model_validate(r) for r in config_repo.listar(db)]


@router.post("/config/regras-alerta", response_model=RegraAlertaOut, status_code=201,
             summary="Cria uma regra de alerta")
def criar_regra(payload: RegraAlertaCreate, ctx: TenantContext = Depends(_ESCREVER),
                db: Session = Depends(get_tenant_db)) -> RegraAlertaOut:
    if indicadores.obter(payload.entidade, payload.indicador) is None:
        raise HTTPException(422, f"indicador '{payload.indicador}' inválido para entidade '{payload.entidade}'")
    limite = settings_catalog.get_value(db, ctx.tenant_id, "limits.max_alert_rules")
    if config_repo.contar(db) >= limite:
        raise ApiError("invalid_request", f"Limite contratual de {limite} regras atingido.")
    regra = config_repo.criar(
        db, payload.model_dump(),
        auditar=lambda r: audit.add(db, "alert_rule.created", actor=ctx.actor, tenant_id=ctx.tenant_id,
                                    entity_type="regra_alerta", entity_id=r.id,
                                    details={"indicador": r.indicador, "entidade": r.entidade}),
    )
    return RegraAlertaOut.model_validate(regra)


@router.get("/config/regras-alerta/{id_regra}", response_model=RegraAlertaOut)
def obter_regra(id_regra: int, _ctx: TenantContext = Depends(_LER),
                db: Session = Depends(get_tenant_db)) -> RegraAlertaOut:
    regra = config_repo.obter(db, id_regra)
    if regra is None:
        raise HTTPException(404, "regra não encontrada")
    return RegraAlertaOut.model_validate(regra)


@router.put("/config/regras-alerta/{id_regra}", response_model=RegraAlertaOut,
            summary="Atualiza uma regra de alerta")
def atualizar_regra(id_regra: int, payload: RegraAlertaUpdate, ctx: TenantContext = Depends(_ESCREVER),
                    db: Session = Depends(get_tenant_db)) -> RegraAlertaOut:
    atual = config_repo.obter(db, id_regra)
    if atual is None:
        raise HTTPException(404, "regra não encontrada")
    dados = payload.model_dump(exclude_unset=True)
    if "entidade" in dados or "indicador" in dados:
        ent = dados.get("entidade", atual.entidade)
        ind = dados.get("indicador", atual.indicador)
        if indicadores.obter(ent, ind) is None:
            raise HTTPException(422, f"indicador '{ind}' inválido para entidade '{ent}'")
    regra = config_repo.atualizar(
        db, id_regra, dados,
        auditar=lambda r: audit.add(db, "alert_rule.updated", actor=ctx.actor, tenant_id=ctx.tenant_id,
                                    entity_type="regra_alerta", entity_id=r.id,
                                    details={"campos": sorted(dados)}),
    )
    return RegraAlertaOut.model_validate(regra)


@router.delete("/config/regras-alerta/{id_regra}", status_code=204, response_model=None,
               summary="Exclui uma regra de alerta")
def excluir_regra(id_regra: int, ctx: TenantContext = Depends(_ESCREVER),
                  db: Session = Depends(get_tenant_db)) -> None:
    ok = config_repo.excluir(
        db, id_regra,
        auditar=lambda r: audit.add(db, "alert_rule.deleted", actor=ctx.actor, tenant_id=ctx.tenant_id,
                                    entity_type="regra_alerta", entity_id=r.id,
                                    details={"nome": r.nome}),
    )
    if not ok:
        raise HTTPException(404, "regra não encontrada")


@router.get("/analytics/alertas", summary="Alertas configurados, avaliados contra o período",
            dependencies=[Depends(require_feature("alerts"))])
def alertas_avaliados(
    competencia: date = Depends(competencia_dep),
    comparacao: str = Depends(comparacao_dep),
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_tenant_db),
) -> dict:
    itens = filter_alertas([a.as_dict() for a in alerts.avaliar_regras(db, competencia, comparacao)],
                           ctx.features)
    return {
        "competencia": competencia.isoformat(),
        "comparacao": comparacao,
        "total": len(itens),
        "itens": itens,
    }
