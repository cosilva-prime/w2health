"""Fixtures compartilhadas dos testes."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    """Cliente de teste sobre uma instância isolada da aplicação."""
    return TestClient(create_app())


# --------------------------------------------------------------------------------------
# Banco de testes com massa sintética pequena e determinística (para os testes de
# cenário e de endpoints). Criado uma vez por sessão de testes em um banco separado.
# --------------------------------------------------------------------------------------
def _base_url() -> str:
    return get_settings().database_url


def _test_url() -> str:
    base = _base_url()
    return os.environ.get("TEST_DATABASE_URL") or base.rsplit("/", 1)[0] + "/w2health_test"


def _db_disponivel(url: str) -> bool:
    try:
        create_engine(url).connect().close()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def seeded_sessionmaker():
    """Cria/recria `w2health_test`, aplica o schema, gera 6.000 beneficiários com cenários.

    Pula todos os testes que dependem de banco se o PostgreSQL não estiver acessível.
    """
    base_url = _base_url()
    test_url = _test_url()
    if not _db_disponivel(base_url):
        pytest.skip("PostgreSQL indisponível — testes de banco pulados")

    admin = create_engine(base_url, isolation_level="AUTOCOMMIT")
    dbname = test_url.rsplit("/", 1)[1]
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)'))
        c.execute(text(f'CREATE DATABASE "{dbname}"'))
    admin.dispose()

    engine = create_engine(test_url, future=True)
    import app.models  # noqa: F401  (registra tabelas na metadata)
    from app.db.base import Base

    Base.metadata.create_all(engine)
    Maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    from app.seed.config import SeedConfig
    from app.seed.run import run_seed

    with Maker() as s:
        run_seed(SeedConfig(n_beneficiarios=6000, seed=42), s, verbose=False)

    yield Maker
    engine.dispose()


@pytest.fixture
def db(seeded_sessionmaker) -> Session:
    s = seeded_sessionmaker()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def gabarito(db) -> dict:
    from app.repositories import analytics_repo as repo

    return {g["codigo"]: g for g in repo.gabarito(db)}
