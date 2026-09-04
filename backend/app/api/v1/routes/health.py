"""Endpoint de health check."""

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import get_engine

router = APIRouter(tags=["Infraestrutura"])


class HealthResponse(BaseModel):
    """Resposta do health check."""

    status: str
    service: str
    version: str
    environment: str
    database: str
    timestamp: str


@router.get("/health", response_model=HealthResponse, summary="Health check da API")
def health() -> HealthResponse:
    """Retorna o estado da API + conectividade com o banco.

    Usado pelo frontend (cartão "Status do ambiente") e pelo healthcheck do Docker.
    """
    settings = get_settings()

    database = "ok"
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - health não deve levantar
        database = "unavailable"

    return HealthResponse(
        status="ok" if database == "ok" else "degraded",
        service=settings.project_name,
        version=settings.version,
        environment=settings.environment,
        database=database,
        timestamp=datetime.now(UTC).isoformat(),
    )
