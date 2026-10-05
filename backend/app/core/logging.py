"""Logging estruturado (JSON) com correlação.

Todo registro carrega, quando houver: `request_id`/`correlation_id`, `tenant_id`,
`pipeline_run_id`, `ingestion_run_id`, `source_connection_id` — vindos de um contexto
(`log_context`) preenchido pelo middleware HTTP e pelo pipeline. Assim dá para responder
"por que a carga do tenant X falhou?" filtrando os logs, sem abrir o banco.

NUNCA logar: senha, token, segredo, código MFA, payload assistencial, PII desnecessária.
Campos `extra` com nomes sensíveis são redigidos (`[REDACTED]`) por precaução.
"""

import json
import logging
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime

_CONFIGURED = False
_ctx: ContextVar[dict | None] = ContextVar("w2h_log_ctx", default=None)

_CAMPOS_CTX = ("request_id", "correlation_id", "tenant_id", "pipeline_run_id",
               "ingestion_run_id", "source_connection_id")
_SENSIVEIS = ("password", "senha", "token", "secret", "segredo", "authorization", "cookie",
              "payload", "codigo_mfa", "otp")
_PADRAO = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


@contextmanager
def log_context(**campos):
    atual = dict(_ctx.get() or {})
    atual.update({k: v for k, v in campos.items() if v is not None})
    token = _ctx.set(atual)
    try:
        yield
    finally:
        _ctx.reset(token)


def set_log_context(**campos) -> None:
    atual = dict(_ctx.get() or {})
    atual.update({k: v for k, v in campos.items() if v is not None})
    _ctx.set(atual)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        out.update(_ctx.get() or {})
        for k, v in record.__dict__.items():
            if k in _PADRAO or k.startswith("_"):
                continue
            out[k] = "[REDACTED]" if any(s in k.lower() for s in _SENSIVEIS) else v
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, default=str, ensure_ascii=False)


def configure_logging(level: int = logging.INFO, fmt: str | None = None) -> None:
    """Configura um handler em stdout. Idempotente."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    if fmt is None:
        from app.core.config import get_settings

        fmt = get_settings().log_format
    handler = logging.StreamHandler(sys.stdout)
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s", datefmt="%Y-%m-%dT%H:%M:%S%z"))
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]
    _CONFIGURED = True
