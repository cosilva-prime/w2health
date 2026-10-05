# W2Health Intelligence — Backend

API REST em **FastAPI**. Ambiente demonstrativo com dados sintéticos.

## Estrutura (Fundação SaaS V1)

- `app/analytics/` — motor analítico (inalterado pela V1)
- `app/repositories/` — SQL tenant-scoped, fail-closed (`app/db/tenant_scope.py`)
- `app/security/` — senhas (argon2id), tokens (JWT/refresh), MFA (TOTP), RBAC, dependências
- `app/saas/` — features, planos, branding, configurações, segredos, auditoria, usuários, CLI
- `app/api/v1/routes/` — `auth`, `admin`, `tenant_admin`, `public` + rotas analíticas
- Docs: `docs/V1_SAAS_FOUNDATION.md`, `docs/SECURITY_AND_TENANT_ISOLATION.md`

## Rodar localmente (sem Docker)

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8010
# http://localhost:8010/docs
```

> Porta `8010` para não colidir com o Docker Desktop, que ocupa a `8000` nesta máquina.

## Testes

```bash
uv run pytest
```

## Dependências

Desenvolvimento: `uv` com `pyproject.toml` + `uv.lock`.
Imagem Docker: `requirements.txt` (gerado do lock), instalado com `pip` — evita depender
de registries além de PyPI e Docker Hub. Regenerar após alterar dependências:

```bash
uv export --no-emit-project --no-hashes --format requirements-txt -o requirements.txt
```

## Variáveis de ambiente

| Variável         | Default                                                             | Uso                          |
|------------------|--------------------------------------------------------------------|------------------------------|
| `PROJECT_NAME`   | `W2Health Intelligence`                                            | título da API                |
| `ENVIRONMENT`    | `development`                                                      | rótulo de ambiente           |
| `API_V1_PREFIX`  | `/api`                                                            | prefixo das rotas v1         |
| `CORS_ORIGINS`   | `http://localhost:3000`                                           | origens permitidas (CSV)     |
| `DATABASE_URL`   | `postgresql+psycopg://w2health:w2health@localhost:5432/w2health`  | papel de RUNTIME da API (sem superusuário — RLS) |
| `DATABASE_ADMIN_URL` | — (cai para `DATABASE_URL`) | papel DONO: migrations, seed, CLI |
| `APP_DB_PASSWORD` | — | senha do papel `w2health_app` (migration de RLS) |
| `JWT_SECRET_KEY` | — (efêmera em dev) | assinatura dos access tokens — obrigatória em produção |
| `DATA_ENCRYPTION_KEY` | — | chave(s) Fernet p/ MFA e segredos — obrigatória em produção |
| `COOKIE_SECURE` | `false` | `true` fora de desenvolvimento |
