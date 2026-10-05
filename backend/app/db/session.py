"""Engines e sessões do SQLAlchemy (síncrono).

* `get_engine()` / `SessionLocal` / `get_db` — papel de RUNTIME da API (`DATABASE_URL`).
* `get_admin_engine()` / `AdminSessionLocal` — papel DONO (`DATABASE_ADMIN_URL`), usado só
  por processos privilegiados de linha de comando (seed, agregação, bootstrap). Nunca é
  exposto por uma rota HTTP.
"""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.tenant_scope  # noqa: F401  (registra o listener que propaga o tenant ao RLS)
from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """Cria (uma vez) o engine de runtime a partir de `DATABASE_URL`."""
    settings = get_settings()
    return create_engine(settings.database_url, pool_pre_ping=True, future=True)


@lru_cache
def get_admin_engine() -> Engine:
    """Engine do papel dono do schema (CLI/jobs). Cai para `DATABASE_URL` se não configurado."""
    settings = get_settings()
    return create_engine(settings.admin_database_url, pool_pre_ping=True, future=True)


SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def AdminSessionLocal() -> Session:  # noqa: N802 — mesma ergonomia de um sessionmaker
    return Session(bind=get_admin_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Dependência do FastAPI: fornece uma sessão e garante o fechamento."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
