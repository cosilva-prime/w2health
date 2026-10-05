"""Engine/sessão do papel de PIPELINE (`w2health_pipeline`).

Três papéis de banco, três responsabilidades (docs/PIPELINE_ARCHITECTURE.md §Papéis):

| papel             | quem usa                    | privilégios                                  |
|-------------------|-----------------------------|----------------------------------------------|
| `w2health_app`    | API (requisições)           | leitura do data plane + config; RLS          |
| `w2health_pipeline` | execuções de pipeline     | escrita no data plane do tenant amarrado; RLS |
| dono (`w2health`) | migrations / CLI de bootstrap | DDL; nunca usado pela aplicação            |

Sem `DATABASE_PIPELINE_URL` o pipeline NÃO executa — não há fallback para o dono.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

import app.db.tenant_scope  # noqa: F401  (listener que propaga o tenant ao RLS)
from app.core.config import get_settings

_engine: Engine | None = None


class PipelineDatabaseNotConfigured(RuntimeError):
    pass


def get_pipeline_engine() -> Engine:
    global _engine
    if _engine is None:
        url = get_settings().database_pipeline_url
        if not url:
            raise PipelineDatabaseNotConfigured(
                "DATABASE_PIPELINE_URL não configurada — pipelines exigem o papel w2health_pipeline")
        _engine = create_engine(url, pool_pre_ping=True, future=True)
    return _engine


def set_pipeline_engine(engine: Engine | None) -> None:
    """Injeção para testes."""
    global _engine
    _engine = engine


def PipelineSession() -> Session:  # noqa: N802 — mesma ergonomia de um sessionmaker
    return Session(bind=get_pipeline_engine(), autoflush=False, expire_on_commit=False)
