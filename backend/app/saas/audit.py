"""Trilha de auditoria (`audit_logs`).

Dois modos de gravação:

* `add(session, ...)` — na MESMA transação da mudança auditada (atômico: se a mudança não
  for confirmada, a auditoria também não é; e vice-versa). Usar em toda mutação
  administrativa.
* `record_independent(bind, ...)` — em transação própria, confirmada mesmo que a requisição
  falhe. Usar em eventos sem mudança de estado de negócio: falha de login, acesso negado,
  reuso de refresh token.

`sanitize` remove recursivamente qualquer chave com cara de segredo (senha, token, código
MFA, credencial, cookie…) e trunca textos — a trilha nunca guarda segredo nem conteúdo
clínico. IP/User-Agent/request id vêm do contexto da requisição (middleware em `main.py`).
"""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog

log = logging.getLogger(__name__)

_SENSIVEIS = (
    "password", "senha", "token", "secret", "segredo", "mfa_code", "codigo_mfa", "otp", "totp",
    "authorization", "cookie", "refresh", "credential", "credencial", "api_key", "apikey",
    "ciphertext", "private", "hash",
)
_MAX_STR = 300
_MAX_DEPTH = 4


@dataclass
class RequestMeta:
    ip: str | None = None
    user_agent: str | None = None
    request_id: str | None = None


_request_meta: ContextVar[RequestMeta | None] = ContextVar("w2h_request_meta", default=None)


def set_request_meta(meta: RequestMeta) -> None:
    _request_meta.set(meta)


def current_request_meta() -> RequestMeta:
    return _request_meta.get() or RequestMeta()


def _sensivel(chave: str) -> bool:
    k = chave.lower()
    return any(s in k for s in _SENSIVEIS)


def sanitize(value: Any, depth: int = 0) -> Any:
    if depth > _MAX_DEPTH:
        return "[…]"
    if isinstance(value, dict):
        return {
            str(k): ("[REDACTED]" if _sensivel(str(k)) else sanitize(v, depth + 1))
            for k, v in list(value.items())[:50]
        }
    if isinstance(value, (list, tuple, set)):
        return [sanitize(v, depth + 1) for v in list(value)[:50]]
    if isinstance(value, str):
        return value[:_MAX_STR]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:_MAX_STR]


@dataclass(frozen=True)
class Actor:
    user_id: uuid.UUID | None = None
    email: str | None = None
    role: str | None = None


ANONYMOUS = Actor()


def _build(
    *, action: str, actor: Actor, tenant_id: str | None, entity_type: str | None,
    entity_id: Any, outcome: str, details: dict | None,
) -> AuditLog:
    meta = current_request_meta()
    return AuditLog(
        actor_user_id=actor.user_id,
        actor_email=actor.email,
        actor_role=actor.role,
        tenant_id=tenant_id,
        action=action,
        entity_type=entity_type,
        entity_id=None if entity_id is None else str(entity_id)[:80],
        outcome=outcome,
        ip=meta.ip,
        user_agent=(meta.user_agent or "")[:200] or None,
        request_id=meta.request_id,
        details=sanitize(details or {}),
    )


def add(
    session: Session, action: str, *, actor: Actor, tenant_id: str | None = None,
    entity_type: str | None = None, entity_id: Any = None, outcome: str = "success",
    details: dict | None = None,
) -> None:
    session.add(_build(action=action, actor=actor, tenant_id=tenant_id, entity_type=entity_type,
                       entity_id=entity_id, outcome=outcome, details=details))


def record_independent(
    bind, action: str, *, actor: Actor = ANONYMOUS, tenant_id: str | None = None,
    entity_type: str | None = None, entity_id: Any = None, outcome: str = "failure",
    details: dict | None = None,
) -> None:
    """Grava em sessão/transação própria sobre o MESMO engine da requisição."""
    try:
        with Session(bind=bind) as s:
            s.add(_build(action=action, actor=actor, tenant_id=tenant_id,
                         entity_type=entity_type, entity_id=entity_id, outcome=outcome,
                         details=details))
            s.commit()
    except Exception:  # noqa: BLE001 — auditoria de falha nunca derruba a resposta
        log.exception("falha ao gravar auditoria independente (action=%s)", action)


def data_access(bind, *, actor: Actor, tenant_id: str, action: str, entity_type: str,
                entity_id=None, details: dict | None = None) -> None:
    """Auditoria de LEITURA de dado individual sensível (beneficiário, eventos, drill-down).

    Registra quem, quando, qual tenant, qual entidade e o id TÉCNICO — nunca conteúdo
    clínico (procedimentos, diagnósticos, valores) nem o payload devolvido."""
    record_independent(bind, action, actor=actor, tenant_id=tenant_id, entity_type=entity_type,
                       entity_id=entity_id, outcome="success", details=details or {})
