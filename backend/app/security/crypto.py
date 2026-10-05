"""Criptografia simétrica de segredos em repouso (MFA, credenciais de integração).

Fernet (AES-128-CBC + HMAC-SHA256) via `cryptography`. `DATA_ENCRYPTION_KEY` aceita várias
chaves separadas por vírgula (MultiFernet): a primeira cifra, todas decifram — rotação sem
downtime. Sem chave configurada, as operações levantam `EncryptionUnavailable` (nunca há
fallback para texto puro).
"""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import get_settings


class EncryptionUnavailable(RuntimeError):
    """DATA_ENCRYPTION_KEY ausente ou inválida."""


@lru_cache
def _fernet() -> MultiFernet:
    key = get_settings().data_encryption_key
    if key is None or not key.get_secret_value().strip():
        raise EncryptionUnavailable("DATA_ENCRYPTION_KEY não configurada")
    try:
        chaves = [Fernet(k.strip().encode()) for k in key.get_secret_value().split(",") if k.strip()]
    except (ValueError, TypeError) as e:
        raise EncryptionUnavailable("DATA_ENCRYPTION_KEY inválida") from e
    return MultiFernet(chaves)


def encryption_available() -> bool:
    try:
        _fernet()
        return True
    except EncryptionUnavailable:
        return False


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as e:
        raise EncryptionUnavailable("segredo ilegível com as chaves atuais") from e


def reset_cache() -> None:
    """Para testes que trocam a chave em tempo de execução."""
    _fernet.cache_clear()
