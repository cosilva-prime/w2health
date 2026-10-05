"""Cofre de segredos por tenant (credenciais de integração futuras).

* Valor cifrado com Fernet (`app/security/crypto.py`) antes de tocar o banco.
* A API é **write-only**: lista metadados (chave, datas), nunca o valor — nem mascarado.
* `reveal()` existe só para uso interno de conectores (fase futura) e não é exposto por rota.
* `source_connections.config` referencia segredos por nome (`{"secret_ref": "<chave>"}`).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TenantSecret
from app.security import crypto

_KEY = re.compile(r"^[a-z0-9][a-z0-9_.-]{1,78}$")
MAX_VALUE = 8 * 1024


class SecretError(ValueError):
    pass


def _check_key(key: str) -> None:
    if not _KEY.match(key or ""):
        raise SecretError("chave inválida (use a-z, 0-9, '_', '.', '-')")


def put(session: Session, tenant_id: str, key: str, value: str, *, user_id=None) -> bool:
    """Cria ou rotaciona. Retorna True se foi rotação. Não faz commit."""
    _check_key(key)
    if not isinstance(value, str) or not value or len(value) > MAX_VALUE:
        raise SecretError("valor vazio ou grande demais")
    cifrado = crypto.encrypt(value)
    row = session.get(TenantSecret, (tenant_id, key))
    if row is None:
        session.add(TenantSecret(tenant_id=tenant_id, key=key, ciphertext=cifrado, created_by=user_id))
        session.flush()
        return False
    row.ciphertext = cifrado
    row.rotated_at = datetime.now(UTC)
    session.flush()
    return True


def list_metadata(session: Session, tenant_id: str) -> list[dict]:
    rows = session.execute(
        select(TenantSecret).where(TenantSecret.tenant_id == tenant_id).order_by(TenantSecret.key)
    ).scalars()
    return [
        {"key": r.key, "created_at": r.created_at.isoformat() if r.created_at else None,
         "rotated_at": r.rotated_at.isoformat() if r.rotated_at else None}
        for r in rows
    ]


def delete(session: Session, tenant_id: str, key: str) -> bool:
    row = session.get(TenantSecret, (tenant_id, key))
    if row is None:
        return False
    session.delete(row)
    session.flush()
    return True


def reveal(session: Session, tenant_id: str, key: str) -> str | None:
    """USO INTERNO (conectores). Nunca devolver por API nem logar."""
    row = session.get(TenantSecret, (tenant_id, key))
    return None if row is None else crypto.decrypt(row.ciphertext)
