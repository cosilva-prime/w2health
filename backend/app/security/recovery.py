"""Códigos de recuperação de MFA.

* 10 códigos de ~50 bits (formato `XXXXX-XXXXX`, alfabeto base32 sem ambíguos), gerados
  no servidor e exibidos UMA única vez;
* persistidos só como hash argon2id (`user_recovery_codes`); uso único (`used_at`);
* gerar de novo apaga TODOS os anteriores; reset administrativo de MFA também;
* nunca aparecem em log ou auditoria (a auditoria registra só a ação e a quantidade).
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import UserRecoveryCode
from app.security.passwords import hash_password, verify_password

QUANTIDADE = 10
_ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _novo() -> str:
    s = "".join(secrets.choice(_ALFABETO) for _ in range(10))
    return f"{s[:5]}-{s[5:]}"


def _normalizar(code: str) -> str:
    c = (code or "").strip().upper().replace(" ", "").replace("-", "")
    return f"{c[:5]}-{c[5:]}" if len(c) == 10 else ""


def generate(session: Session, user_id: uuid.UUID) -> list[str]:
    """Substitui os códigos do usuário. Retorna os códigos em claro (exibir uma vez)."""
    session.execute(delete(UserRecoveryCode).where(UserRecoveryCode.user_id == user_id))
    codigos = [_novo() for _ in range(QUANTIDADE)]
    session.add_all(UserRecoveryCode(user_id=user_id, code_hash=hash_password(c)) for c in codigos)
    session.flush()
    return codigos


def consume(session: Session, user_id: uuid.UUID, code: str) -> bool:
    alvo = _normalizar(code)
    if not alvo:
        return False
    for rc in session.execute(select(UserRecoveryCode).where(
            UserRecoveryCode.user_id == user_id, UserRecoveryCode.used_at.is_(None))).scalars():
        if verify_password(rc.code_hash, alvo):
            rc.used_at = datetime.now(UTC)
            session.flush()
            return True
    return False


def remaining(session: Session, user_id: uuid.UUID) -> int:
    return session.execute(select(func.count()).select_from(UserRecoveryCode).where(
        UserRecoveryCode.user_id == user_id, UserRecoveryCode.used_at.is_(None))).scalar_one()


def clear(session: Session, user_id: uuid.UUID) -> None:
    session.execute(delete(UserRecoveryCode).where(UserRecoveryCode.user_id == user_id))
    session.flush()
