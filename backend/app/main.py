"""Ponto de entrada da aplicação FastAPI do W2Health Intelligence.

Ambiente demonstrativo — todos os dados do produto são sintéticos.
Etapa 1 do MVP: apenas fundações (health check, configuração, CORS).
"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> Any:
    """Hook de startup/shutdown — configura logging na subida."""
    configure_logging()
    yield


def create_app() -> FastAPI:
    """Factory da aplicação — facilita instâncias isoladas nos testes."""
    app = FastAPI(
        title=settings.project_name,
        description=(
            "Decision Intelligence Platform for Healthcare — API REST. "
            "Ambiente demonstrativo com dados sintéticos."
        ),
        version=settings.version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)

    @app.get("/", tags=["Infraestrutura"], summary="Metadados da API")
    def root() -> dict[str, str]:
        return {
            "service": settings.project_name,
            "version": settings.version,
            "docs": "/docs",
            "health": f"{settings.api_v1_prefix}/health",
        }

    return app


app = create_app()
