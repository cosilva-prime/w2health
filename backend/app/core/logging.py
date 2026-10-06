"""Logging estruturado (JSON) com correlação.

Todo registro carrega `timestamp`, `level`, `service` (api/worker/cli), `environment`,
`event` e, quando houver: `request_id`/`correlation_id`, `tenant_id`, `user_id`, `job_id`,
`pipeline_run_id`, `ingestion_run_id`, `source_connection_id`, `duration_ms`, `status` —
vindos de um contexto (`log_context`) preenchido pelo middleware HTTP, pelo worker e pelo
pipeline. O worker abre um contexto LIMPO por job (`fresh_log_context`): nenhum campo de um
job anterior (tenant, ids) vaza para o próximo. Assim dá para responder
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

_CAMPOS_CTX = ("request_id", "correlation_id", "tenant_id", "user_id", "job_id", "pipeline_run_id",
               "ingestion_run_id", "source_connection_id")
_SENSIVEIS = ("password", "senha", "token", "secret", "segredo", "authorization", "cookie",
              "payload", "codigo_mfa", "otp")
_PADRAO = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime", "event"}
#: (service, environment) — definidos em configure_logging
_SERVICE = ["api", "development"]


@contextmanager
def log_context(**campos):
    atual = dict(_ctx.get() or {})
    atual.update({k: v for k, v in campos.items() if v is not None})
    token = _ctx.set(atual)
    try:
        yield
    finally:
        _ctx.reset(token)


@contextmanager
def fresh_log_context(**campos):
    """Substitui (não mescla) o contexto — usado pelo worker a cada job."""
    token = _ctx.set({k: v for k, v in campos.items() if v is not None})
    try:
        yield
    finally:
        _ctx.reset(token)


def clear_log_context() -> None:
    _ctx.set({})


def current_log_context() -> dict:
    return dict(_ctx.get() or {})


def set_log_context(**campos) -> None:
    atual = dict(_ctx.get() or {})
    atual.update({k: v for k, v in campos.items() if v is not None})
    _ctx.set(atual)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "service": _SERVICE[0],
            "environment": _SERVICE[1],
            "logger": record.name,
            "event": getattr(record, "event", None) or record.getMessage(),
            "msg": record.getMessage(),
        }
        out.update(_ctx.get() or {})
        for k, v in record.__dict__.items():
            if k in _PADRAO or k.startswith("_"):
                continue
            out[k] = "[REDACTED]" if any(s in k.lower() for s in _SENSIVEIS) else v
        # exc_info só com o tipo e a mensagem já formatada — mensagens de exceção do
        # pipeline são seguras por construção (sem dado de linha)
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
    from app.core.config import get_settings

    st = get_settings()
    _SERVICE[0], _SERVICE[1] = st.service_name, st.environment
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
