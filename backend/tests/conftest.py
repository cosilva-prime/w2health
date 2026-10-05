"""Fixtures compartilhadas dos testes.

Fundação SaaS V1 — adaptações de INFRAESTRUTURA de teste (nenhuma asserção antiga mudou):
* o banco de testes é criado com o papel DONO (`DATABASE_ADMIN_URL`), com as duas metadatas
  (data plane + control plane);
* após o seed, o catálogo de features/planos é sincronizado, o tenant demo recebe o plano
  ENTERPRISE (o mesmo backfill da migration) e são criados usuários de teste por papel;
* `db` devolve uma sessão já amarrada ao tenant demo (os repositórios são fail-closed);
* `auth_headers` fornece um access token real de um MANAGER do tenant demo — usado pelas
  fixtures `api` dos testes de endpoint, que agora exigem autenticação.
"""

from __future__ import annotations

import os
import secrets

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.tenant import DEFAULT_TENANT
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    """Cliente de teste sobre uma instância isolada da aplicação."""
    return TestClient(create_app())


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    """O limitador por IP é global ao processo; cada teste começa zerado."""
    from app.api.v1.routes.auth import auth_limiter

    auth_limiter.reset()
    yield


# --------------------------------------------------------------------------------------
# Banco de testes com massa sintética pequena e determinística (para os testes de
# cenário e de endpoints). Criado uma vez por sessão de testes em um banco separado.
# --------------------------------------------------------------------------------------
def _base_url() -> str:
    return get_settings().admin_database_url


def _test_url() -> str:
    base = _base_url()
    return os.environ.get("TEST_DATABASE_URL") or base.rsplit("/", 1)[0] + "/w2health_test"


def _db_disponivel(url: str) -> bool:
    try:
        create_engine(url).connect().close()
        return True
    except Exception:
        return False


def recreate_database(dbname: str):
    """(Re)cria um banco de testes vazio e devolve o engine (papel dono)."""
    base_url = _base_url()
    if not _db_disponivel(base_url):
        pytest.skip("PostgreSQL indisponível — testes de banco pulados")
    admin = create_engine(base_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)'))
        c.execute(text(f'CREATE DATABASE "{dbname}"'))
    admin.dispose()
    url = base_url.rsplit("/", 1)[0] + "/" + dbname
    return create_engine(url, future=True), url


TEST_PASSWORD = "Teste-" + secrets.token_urlsafe(12)

#: e-mail → (papel de tenant, papel de plataforma) dos usuários do tenant demo nos testes
TEST_USERS = {
    "tenant_admin@test.example": ("TENANT_ADMIN", None),
    "manager@test.example": ("MANAGER", None),
    "viewer@test.example": ("VIEWER", None),
}


def bootstrap_saas(session: Session, tenant_id: str = DEFAULT_TENANT, plan_code: str = "ENTERPRISE",
                   users: dict | None = None) -> None:
    """Catálogo + plano do tenant + usuários de teste (idempotente)."""
    from app.models import Plan, Tenant, User, UserTenant
    from app.saas.catalog import sync_catalog
    from app.security.passwords import hash_password

    sync_catalog(session)
    t = session.get(Tenant, tenant_id)
    t.plan_id = session.execute(select(Plan.id).where(Plan.code == plan_code)).scalar_one()
    senha_hash = hash_password(TEST_PASSWORD)
    for email, (papel, plataforma) in (users or TEST_USERS).items():
        u = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if u is None:
            u = User(email=email, name=email.split("@")[0], password_hash=senha_hash,
                     platform_role=plataforma)
            session.add(u)
            session.flush()
        if papel and session.get(UserTenant, (u.id, tenant_id)) is None:
            session.add(UserTenant(user_id=u.id, tenant_id=tenant_id, role=papel))
    session.commit()


def token_for(session: Session, email: str, tenant_id: str | None) -> str:
    """Access token real (sessão persistida) — sem passar pelo fluxo de login/MFA."""
    from app.models import User
    from app.security.sessions import create_session

    u = session.execute(select(User).where(User.email == email)).scalar_one()
    emitido = create_session(session, u, tenant_id, ip="testclient", user_agent="pytest")
    session.commit()
    return emitido.access_token


@pytest.fixture(scope="session")
def seeded_sessionmaker():
    """Cria/recria `w2health_test`, aplica o schema, gera 6.000 beneficiários com cenários.

    Pula todos os testes que dependem de banco se o PostgreSQL não estiver acessível.
    """
    import app.models  # noqa: F401  (registra tabelas nas metadatas)
    from app.db.base import create_all

    dbname = _test_url().rsplit("/", 1)[1]
    engine, _ = recreate_database(dbname)
    create_all(engine)
    Maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    from app.seed.config import SeedConfig
    from app.seed.run import run_seed

    with Maker() as s:
        run_seed(SeedConfig(n_beneficiarios=6000, seed=42), s, verbose=False)
    with Maker() as s:
        bootstrap_saas(s)

    yield Maker
    engine.dispose()


@pytest.fixture
def db(seeded_sessionmaker) -> Session:
    from app.db.tenant_scope import bind_tenant

    s = seeded_sessionmaker()
    bind_tenant(s, DEFAULT_TENANT)
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(scope="session")
def auth_headers(seeded_sessionmaker) -> dict[str, str]:
    """Cabeçalho Authorization de um MANAGER do tenant demo (todas as features: ENTERPRISE)."""
    with seeded_sessionmaker() as s:
        return {"Authorization": f"Bearer {token_for(s, 'manager@test.example', DEFAULT_TENANT)}"}


@pytest.fixture
def gabarito(db) -> dict:
    from app.repositories import analytics_repo as repo

    return {g["codigo"]: g for g in repo.gabarito(db)}
