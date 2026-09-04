# W2Health Intelligence — Backend

API REST em **FastAPI**. Ambiente demonstrativo com dados sintéticos.

## Etapa 1 (atual)

Apenas fundações:

- `create_app()` factory em [app/main.py](app/main.py)
- Configuração via env / `.env` — [app/core/config.py](app/core/config.py)
- CORS configurável
- `GET /api/health` — [app/api/v1/routes/health.py](app/api/v1/routes/health.py)
- `GET /` — metadados · `GET /docs` — Swagger

Ainda **não** implementado (próximas etapas): modelo de dados, SQLAlchemy/Alembic,
geração de dados sintéticos, motor analítico.

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
| `DATABASE_URL`   | `postgresql+psycopg://w2health:w2health@localhost:5432/w2health`  | reservada para a Etapa 2     |
