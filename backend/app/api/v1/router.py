"""Agregador de rotas da API v1."""

from fastapi import APIRouter

from app.api.v1.routes import (
    admin,
    auth,
    beneficiarios,
    config,
    contratos,
    executive,
    health,
    insights,
    prestadores,
    procedimentos,
    public,
    sinistralidade,
    tenant_admin,
)

api_v1_router = APIRouter()
api_v1_router.include_router(health.router)
api_v1_router.include_router(public.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(admin.router)
api_v1_router.include_router(tenant_admin.router)
api_v1_router.include_router(executive.router)
api_v1_router.include_router(sinistralidade.router)
api_v1_router.include_router(procedimentos.router)
api_v1_router.include_router(prestadores.router)
api_v1_router.include_router(beneficiarios.router)
api_v1_router.include_router(contratos.router)
api_v1_router.include_router(insights.router)
api_v1_router.include_router(config.router)
