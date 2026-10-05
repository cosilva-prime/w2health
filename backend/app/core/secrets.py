"""Abstração de segredos — o código não depende de um provedor específico.

Referências (`secret_reference`) usadas pelas fontes de dados:

* `tenant:<chave>` — cofre por tenant no banco (`tenant_secrets`, Fernet). Padrão.
* `env:<NOME>`     — variável de ambiente (somente DEV/local; recusada em produção).

Produção (docs/SECURITY_AND_TENANT_ISOLATION.md §8): um `SecretProvider` adicional para
o gerenciador da nuvem escolhida (AWS Secrets Manager, Azure Key Vault, GCP Secret
Manager, HashiCorp Vault) implementa o mesmo protocolo com o prefixo `vault:` — nenhum
outro módulo muda. A chave mestra do Fernet (`DATA_ENCRYPTION_KEY`) também deve vir do
gerenciador, não de arquivo.

Nunca versionar senha, token, API key, segredo MFA ou connection string real.
"""

from __future__ import annotations

import os
import re
from typing import Protocol

from sqlalchemy.orm import Session

from app.core.config import get_settings

_REF = re.compile(r"^(tenant|env|vault):([A-Za-z0-9_.\-/]{2,100})$")


class SecretReferenceError(ValueError):
    pass


class SecretProvider(Protocol):
    def get(self, name: str) -> str | None: ...


class EnvSecretProvider:
    def get(self, name: str) -> str | None:
        return os.environ.get(name)


def validate_reference(ref: str) -> tuple[str, str]:
    m = _REF.match(ref or "")
    if not m:
        raise SecretReferenceError("secret_reference inválida (use tenant:<chave>, env:<NOME> ou vault:<id>)")
    scheme, name = m.groups()
    if scheme == "env" and get_settings().is_production_like:
        raise SecretReferenceError("env: não é permitido em produção — use o cofre")
    return scheme, name


def resolve(ref: str, *, session: Session | None = None, tenant_id: str | None = None) -> str | None:
    """Resolve uma referência. USO INTERNO de conectores — nunca devolver por API nem logar."""
    scheme, name = validate_reference(ref)
    if scheme == "env":
        return EnvSecretProvider().get(name)
    if scheme == "tenant":
        if session is None or not tenant_id:
            raise SecretReferenceError("tenant: exige sessão e tenant")
        from app.saas.secrets import reveal

        return reveal(session, tenant_id, name)
    raise SecretReferenceError("provedor 'vault' ainda não configurado neste ambiente")
