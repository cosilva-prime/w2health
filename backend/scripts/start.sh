#!/bin/sh
# Entrypoint do container backend: aplica migrations e sobe a API.
set -e

echo "[start] aplicando migrations (alembic upgrade head)..."
alembic upgrade head

echo "[start] iniciando uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
