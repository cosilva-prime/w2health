"""Emissão e validação de tokens.

* **Access token** — JWT HS256 curto (`ACCESS_TOKEN_MINUTES`, padrão 15 min). Claims:
  `sub` (user id), `sid` (sessão), `tid` (tenant ativo ou null), `ver` (token_version do
  usuário), `typ="access"`, `iss`, `aud`, `iat`, `exp`, `jti`. **Papel e permissões NÃO
  vão no token** como fonte de autoridade: são relidos do banco a cada requisição.
* **Challenge token** — JWT de 5 min com `typ` restrito (`mfa`, `password_change`,
  `mfa_setup`): serve só para concluir o login, nunca para acessar dados.
* **Refresh token** — opaco (256 bits aleatórios), persistido só como SHA-256, trafega em
  cookie httpOnly; rotacionado a cada uso (`app/security/sessions.py`).

`algorithms=["HS256"]` é fixo na decodificação (impede `alg=none`/troca de algoritmo).
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

import jwt

from app.core.config import get_settings

log = logging.getLogger(__name__)

ALGORITHM = "HS256"
TYP_ACCESS = "access"
CHALLENGE_TYPES = frozenset({"mfa", "password_change", "mfa_setup"})


class TokenError(Exception):
    """Token inválido, expirado ou de tipo errado (mensagem nunca é exposta ao cliente)."""


@lru_cache
def _signing_key() -> str:
    s = get_settings()
    if s.jwt_secret_key is not None and len(s.jwt_secret_key.get_secret_value()) >= 32:
        return s.jwt_secret_key.get_secret_value()
    if s.is_production_like:
        raise RuntimeError("JWT_SECRET_KEY obrigatória em produção/staging")
    log.warning(
        "JWT_SECRET_KEY ausente: usando chave EFÊMERA (somente desenvolvimento) — "
        "as sessões caem a cada reinício do processo."
    )
    return secrets.token_urlsafe(48)


def _now() -> datetime:
    return datetime.now(UTC)


def _encode(claims: dict[str, Any]) -> str:
    s = get_settings()
    base = {"iss": s.jwt_issuer, "aud": s.jwt_audience, "iat": _now(), "jti": uuid.uuid4().hex}
    return jwt.encode({**base, **claims}, _signing_key(), algorithm=ALGORITHM)


def _decode(token: str) -> dict[str, Any]:
    s = get_settings()
    try:
        return jwt.decode(
            token,
            _signing_key(),
            algorithms=[ALGORITHM],
            audience=s.jwt_audience,
            issuer=s.jwt_issuer,
            options={"require": ["exp", "iat", "sub", "typ", "iss", "aud"]},
        )
    except jwt.ExpiredSignatureError as e:
        raise TokenError("expired") from e
    except jwt.PyJWTError as e:
        raise TokenError("invalid") from e


def create_access_token(
    *, user_id: uuid.UUID, session_id: uuid.UUID, tenant_id: str | None, token_version: int
) -> tuple[str, int]:
    minutos = get_settings().access_token_minutes
    token = _encode(
        {
            "sub": str(user_id),
            "sid": str(session_id),
            "tid": tenant_id,
            "ver": token_version,
            "typ": TYP_ACCESS,
            "exp": _now() + timedelta(minutes=minutos),
        }
    )
    return token, minutos * 60


def decode_access_token(token: str) -> dict[str, Any]:
    claims = _decode(token)
    if claims.get("typ") != TYP_ACCESS or "sid" not in claims or "ver" not in claims:
        raise TokenError("wrong_type")
    return claims


def create_challenge_token(
    *, user_id: uuid.UUID, typ: str, token_version: int, tenant_hint: str | None = None
) -> str:
    if typ not in CHALLENGE_TYPES:
        raise ValueError(typ)
    return _encode(
        {
            "sub": str(user_id),
            "typ": typ,
            "ver": token_version,
            "tnh": tenant_hint,
            "exp": _now() + timedelta(minutes=get_settings().challenge_token_minutes),
        }
    )


def decode_challenge_token(token: str, *, expected: set[str]) -> dict[str, Any]:
    claims = _decode(token)
    if claims.get("typ") not in expected:
        raise TokenError("wrong_type")
    return claims


def new_refresh_token() -> tuple[str, str]:
    """(token em claro para o cookie, hash SHA-256 para o banco)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def reset_key_cache() -> None:
    _signing_key.cache_clear()
