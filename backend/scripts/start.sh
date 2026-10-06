#!/bin/sh
# Entrypoint da API.
#
# * RUN_MIGRATIONS=true (padrão só no compose de DESENVOLVIMENTO) aplica as migrations antes
#   de subir. Em produção as migrations rodam num job separado (`migrate`), com o papel dono
#   — o processo da API usa o papel de runtime e não tem privilégio de DDL.
# * --proxy-headers / --forwarded-allow-ips: o IP real do cliente vem de X-Forwarded-For
#   SOMENTE quando a conexão chega de um IP listado (o proxy reverso). Nunca use "*".
# * Log de acesso do uvicorn desligado: a aplicação emite o seu (JSON, com rota-template,
#   status, duração, request_id, tenant e usuário — sem query string nem corpo).
set -e

if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
  echo "[start] aplicando migrations (alembic upgrade head)..."
  alembic upgrade head
fi

echo "[start] iniciando uvicorn..."
exec uvicorn app.main:app \
  --host 0.0.0.0 --port 8000 \
  --workers "${UVICORN_WORKERS:-1}" \
  --proxy-headers --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}" \
  --no-access-log \
  --timeout-graceful-shutdown 25
