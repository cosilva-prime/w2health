# W2Health Intelligence — backend (FastAPI)
#
# Dependências são gerenciadas com `uv` no desenvolvimento (pyproject.toml + uv.lock).
# Para a imagem, usamos o requirements.txt exportado do lock (`uv export`), instalado
# com pip — evita depender de registries externos além de PyPI e Docker Hub.
# Regenerar após mexer nas dependências:
#   cd backend && uv export --no-emit-project --no-hashes --format requirements-txt -o requirements.txt
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Contexto de build = RAIZ do repositório (Fase 2): a imagem embarca a Data Platform
# (contratos, mappings, regras de qualidade) em /data_platform — fonte de verdade lida
# pelo pipeline em tempo de execução.
COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

# Código
COPY backend/ .
COPY data_platform/ /data_platform/

# RAW local (DEV) — fora de qualquer diretório servido; em produção, object storage.
RUN mkdir -p /var/lib/w2health/raw

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health').status==200 else 1)"

# Aplica migrations e sobe a API.
CMD ["sh", "scripts/start.sh"]
