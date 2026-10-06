# W2Health Intelligence — backend (API + worker), build multi-stage.
#
# Alvos:
#   runtime (padrão) — imagem de PRODUÇÃO da API e do worker (mesma imagem, comando muda):
#                      sem compiladores, sem pytest/ruff, sem testes, usuário não-root,
#                      sem .env (segredos só por ambiente/arquivos montados).
#   test             — runtime + dependências de desenvolvimento + testes (CI/`make test`).
#
# Contexto de build = RAIZ do repositório (a Data Platform — contratos, mappings, regras de
# qualidade — vai em /data_platform, lida em tempo de execução).
# Dependências travadas: requirements*.txt exportados do uv.lock
#   cd backend && uv export --no-emit-project --no-hashes --no-dev -o requirements.txt
#   cd backend && uv export --no-emit-project --no-hashes --only-group dev -o requirements-dev.txt
ARG PYTHON_IMAGE=python:3.12-slim-bookworm

FROM ${PYTHON_IMAGE} AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH=/opt/venv/bin:$PATH

# ------------------------------------------------------------------ dependências
FROM base AS deps
RUN python -m venv /opt/venv
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-compile -r /tmp/requirements.txt

FROM deps AS deps-dev
COPY backend/requirements-dev.txt /tmp/requirements-dev.txt
RUN pip install --no-compile -r /tmp/requirements-dev.txt

# ------------------------------------------------------------------ aplicação (comum)
FROM base AS app
RUN groupadd --system --gid 10001 w2h \
 && useradd --system --uid 10001 --gid w2h --no-create-home --shell /usr/sbin/nologin w2h \
 && mkdir -p /var/lib/w2health/raw \
 && chown w2h:w2h /var/lib/w2health/raw
COPY --from=deps /opt/venv /opt/venv
WORKDIR /app
# código somente-leitura para o usuário da aplicação (dono = root)
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini
COPY backend/scripts ./scripts
COPY data_platform/ /data_platform/
ENV DATA_PLATFORM_DIR=/data_platform \
    RAW_STORAGE_ROOT=/var/lib/w2health/raw \
    WORKER_HEARTBEAT_FILE=/tmp/w2h-worker.alive
USER 10001:10001
EXPOSE 8000
# liveness da API (o worker sobrescreve: `python -m app.worker healthcheck`)
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=4).status==200 else 1)"
CMD ["sh", "scripts/start.sh"]

# ------------------------------------------------------------------ testes (CI)
FROM app AS test
USER root
COPY --from=deps-dev /opt/venv /opt/venv
COPY backend/tests ./tests
COPY backend/pyproject.toml ./pyproject.toml
USER 10001:10001
CMD ["pytest", "-q"]

# ------------------------------------------------------------------ runtime (produção)
# ÚLTIMO estágio de propósito: `docker build` sem --target produz a imagem de produção.
FROM app AS runtime
