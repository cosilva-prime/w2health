"""Sessões de login e refresh tokens (rotação com detecção de reuso).

* Uma `AuthSession` tem validade ABSOLUTA (`REFRESH_TOKEN_HOURS`) — refresh não estende.
* Cada refresh consome o token atual (`used_at`) e emite outro. Reapresentar um token já
  consumido = sinal de roubo → a sessão inteira é revogada e o evento é auditado.
* Logout, troca/reset de senha, desativação de usuário e reset de MFA revogam sessões.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AuthSession, RefreshToken, User
from app.security.tokens import create_access_token, hash_refresh_token, new_refresh_token


@dataclass
class IssuedTokens:
    access_token: str
    expires_in: int
    refresh_token: str
    session_id: uuid.UUID
    session_expires_at: datetime


def _now() -> datetime:
    return datetime.now(UTC)


def create_session(
    db: Session, user: User, tenant_id: str | None, *, ip: str | None, user_agent: str | None
) -> IssuedTokens:
    expira = _now() + timedelta(hours=get_settings().refresh_token_hours)
    sess = AuthSession(user_id=user.id, tenant_id=tenant_id, expires_at=expira, ip=ip,
                       user_agent=(user_agent or "")[:200] or None)
    db.add(sess)
    db.flush()
    raw, digest = new_refresh_token()
    db.add(RefreshToken(session_id=sess.id, token_hash=digest, expires_at=expira))
    access, ttl = create_access_token(user_id=user.id, session_id=sess.id, tenant_id=tenant_id,
                                      token_version=user.token_version)
    db.flush()
    return IssuedTokens(access, ttl, raw, sess.id, expira)


class RefreshFailure(Exception):
    def __init__(self, reason: str, session: AuthSession | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.session = session


def rotate(db: Session, raw_token: str) -> tuple[AuthSession, User, str]:
    """Consome o refresh token e devolve (sessão, usuário, novo refresh em claro).

    Levanta `RefreshFailure`; em caso de REUSO a sessão já sai revogada (caller faz commit)."""
    rt = db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
        .with_for_update()
    ).scalar_one_or_none()
    if rt is None:
        raise RefreshFailure("unknown")
    sess = db.get(AuthSession, rt.session_id)
    agora = _now()
    if sess is None:
        raise RefreshFailure("unknown")
    if rt.used_at is not None:
        revoke_session(db, sess, "refresh_reuse")
        raise RefreshFailure("reuse", sess)
    if sess.revoked_at is not None or sess.expires_at <= agora or rt.expires_at <= agora:
        raise RefreshFailure("expired", sess)
    user = db.get(User, sess.user_id)
    if user is None or user.status != "ACTIVE" or user.must_change_password:
        revoke_session(db, sess, "user_inactive")
        raise RefreshFailure("user_inactive", sess)

    rt.used_at = agora
    sess.last_seen_at = agora
    novo_raw, digest = new_refresh_token()
    db.add(RefreshToken(session_id=sess.id, token_hash=digest, expires_at=sess.expires_at))
    db.flush()
    return sess, user, novo_raw


def access_for(sess: AuthSession, user: User) -> tuple[str, int]:
    return create_access_token(user_id=user.id, session_id=sess.id, tenant_id=sess.tenant_id,
                               token_version=user.token_version)


def revoke_session(db: Session, sess: AuthSession, reason: str) -> None:
    if sess.revoked_at is None:
        sess.revoked_at = _now()
        sess.revoked_reason = reason[:40]
    db.flush()


def revoke_all_for_user(db: Session, user_id: uuid.UUID, reason: str) -> int:
    res = db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=_now(), revoked_reason=reason[:40])
    )
    db.flush()
    return res.rowcount or 0


def revoke_all_for_user_in_tenant(db: Session, user_id: uuid.UUID, tenant_id: str, reason: str) -> int:
    res = db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.tenant_id == tenant_id,
               AuthSession.revoked_at.is_(None))
        .values(revoked_at=_now(), revoked_reason=reason[:40])
    )
    db.flush()
    return res.rowcount or 0
