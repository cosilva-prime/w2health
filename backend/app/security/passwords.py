"""Hash e política de senhas — argon2id (argon2-cffi, parâmetros padrão da biblioteca).

* Nunca armazenar/logar senha em claro.
* `verify_password` é tempo-constante no hash; para e-mail inexistente o login verifica
  contra `DUMMY_HASH`, igualando o custo e evitando enumeração de contas por tempo.
* `needs_rehash` permite endurecer parâmetros sem forçar troca de senha.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()

MIN_LENGTH = 12
MAX_LENGTH = 128

# Senhas triviais rejeitadas mesmo com 12+ caracteres. Não é uma lista exaustiva.
_COMUNS = {
    "123456789012", "senha1234567", "password1234", "qwertyuiop12", "w2health1234",
    "administrador", "abcdefghijkl", "000000000000", "111111111111", "senhasenha12",
}

DUMMY_HASH = _hasher.hash("w2h-dummy-password-for-timing")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def password_policy_errors(password: str, *, email: str | None = None) -> list[str]:
    """Erros de política (lista vazia = válida). Mensagens seguras para exibir ao usuário."""
    erros: list[str] = []
    if len(password) < MIN_LENGTH:
        erros.append(f"A senha deve ter ao menos {MIN_LENGTH} caracteres.")
    if len(password) > MAX_LENGTH:
        erros.append(f"A senha deve ter no máximo {MAX_LENGTH} caracteres.")
    if password.lower() in _COMUNS or len(set(password)) < 5:
        erros.append("A senha é muito previsível.")
    if email and email.split("@", 1)[0].lower() in password.lower():
        erros.append("A senha não pode conter o identificador do e-mail.")
    return erros
