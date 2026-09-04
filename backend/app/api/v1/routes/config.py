"""Configuração de regras de alerta (v1.1, Etapa C).

⚠️ DÍVIDA TÉCNICA — endpoints de ESCRITA (POST/PUT/DELETE) sem autenticação/
autorização. Aceitável apenas em ambiente de demonstração local (decisão registrada do
MVP: `docs/DECISOES-MVP.md`). NÃO expor esses endpoints em ambiente real sem controle de
acesso — ver `docs/V1.1.md` § Dívida Técnica.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.analytics import alerts, indicadores
from app.api.v1.routes._common import comparacao_dep, competencia_dep
from app.db.session import get_db
from app.repositories import config_repo
from app.schemas.alertas import RegraAlertaCreate, RegraAlertaOut, RegraAlertaUpdate

router = APIRouter(tags=["Configuração"])


@router.get("/config/indicadores", summary="Catálogo fechado de indicadores para regras de alerta")
def catalogo_indicadores() -> dict:
    return {"itens": indicadores.catalogo_por_entidade()}


@router.get("/config/regras-alerta", response_model=list[RegraAlertaOut], summary="Lista regras de alerta")
def listar_regras(db: Session = Depends(get_db)) -> list[RegraAlertaOut]:
    return [RegraAlertaOut.model_validate(r) for r in config_repo.listar(db)]


@router.post(
    "/config/regras-alerta", response_model=RegraAlertaOut, status_code=201,
    summary="Cria uma regra de alerta (⚠️ sem autenticação — ver docstring do módulo)",
)
def criar_regra(payload: RegraAlertaCreate, db: Session = Depends(get_db)) -> RegraAlertaOut:
    if indicadores.obter(payload.entidade, payload.indicador) is None:
        raise HTTPException(422, f"indicador '{payload.indicador}' inválido para entidade '{payload.entidade}'")
    regra = config_repo.criar(db, payload.model_dump())
    return RegraAlertaOut.model_validate(regra)


@router.get("/config/regras-alerta/{id_regra}", response_model=RegraAlertaOut)
def obter_regra(id_regra: int, db: Session = Depends(get_db)) -> RegraAlertaOut:
    regra = config_repo.obter(db, id_regra)
    if regra is None:
        raise HTTPException(404, "regra não encontrada")
    return RegraAlertaOut.model_validate(regra)


@router.put(
    "/config/regras-alerta/{id_regra}", response_model=RegraAlertaOut,
    summary="Atualiza uma regra de alerta (⚠️ sem autenticação — ver docstring do módulo)",
)
def atualizar_regra(id_regra: int, payload: RegraAlertaUpdate, db: Session = Depends(get_db)) -> RegraAlertaOut:
    atual = config_repo.obter(db, id_regra)
    if atual is None:
        raise HTTPException(404, "regra não encontrada")
    dados = payload.model_dump(exclude_unset=True)
    if "entidade" in dados or "indicador" in dados:
        ent = dados.get("entidade", atual.entidade)
        ind = dados.get("indicador", atual.indicador)
        if indicadores.obter(ent, ind) is None:
            raise HTTPException(422, f"indicador '{ind}' inválido para entidade '{ent}'")
    regra = config_repo.atualizar(db, id_regra, dados)
    return RegraAlertaOut.model_validate(regra)


@router.delete(
    "/config/regras-alerta/{id_regra}", status_code=204, response_model=None,
    summary="Exclui uma regra de alerta (⚠️ sem autenticação — ver docstring do módulo)",
)
def excluir_regra(id_regra: int, db: Session = Depends(get_db)) -> None:
    if not config_repo.excluir(db, id_regra):
        raise HTTPException(404, "regra não encontrada")


@router.get("/analytics/alertas", summary="Alertas configurados, avaliados contra o período")
def alertas_avaliados(
    competencia: date = Depends(competencia_dep),
    comparacao: str = Depends(comparacao_dep),
    db: Session = Depends(get_db),
) -> dict:
    itens = alerts.avaliar_regras(db, competencia, comparacao)
    return {
        "competencia": competencia.isoformat(),
        "comparacao": comparacao,
        "total": len(itens),
        "itens": [a.as_dict() for a in itens],
    }
