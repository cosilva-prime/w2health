"""Source connections — cadastro das fontes de um tenant e validação de conectividade.

Tipos: FILE (implementado nesta fase), DATABASE e API (cadastro aceito, execução ainda
não implementada — nenhum conector real existe), SYNTHETIC (o gerador interno, registrado
para que a linhagem do caminho sintético seja igual à de qualquer outra fonte).

`configuration` só aceita chaves não sensíveis conhecidas; credenciais entram apenas como
`secret_reference` (ver app/core/secrets.py) — nunca em claro.
"""

from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import secrets as secret_provider
from app.data_platform.mapping import Mapping, MappingError, load_mapping_file
from app.data_platform.paths import data_platform_dir
from app.data_platform.storage import get_raw_storage
from app.models import SourceConnection

SOURCE_TYPES = ("FILE", "DATABASE", "API", "SYNTHETIC")
EXECUTABLE_TYPES = ("FILE", "SYNTHETIC")
#: chaves de configuração permitidas (não sensíveis) por tipo
CONFIG_KEYS = {
    "FILE": {"mapping_id", "mapping_version", "description"},
    "DATABASE": {"engine", "host", "port", "database", "schema", "description"},
    "API": {"base_url", "description"},
    "SYNTHETIC": {"description"},
}
_SENSITIVE = re.compile(r"(pass|senha|secret|token|key|credential|credencial)", re.I)
_NAME = re.compile(r"^[\w .()\-/]{3,120}$")
_SYSTEM = re.compile(r"^[a-z][a-z0-9_]{1,59}$")


class ConnectionError_(ValueError):  # noqa: N801 — evita colisão com builtin ConnectionError
    pass


def validate_payload(source_type: str, name: str, source_system: str, configuration: dict,
                     secret_reference: str | None) -> dict:
    if source_type not in SOURCE_TYPES or source_type == "SYNTHETIC":
        raise ConnectionError_("tipo de fonte inválido (FILE, DATABASE ou API)")
    if not _NAME.match(name or ""):
        raise ConnectionError_("nome inválido")
    if not _SYSTEM.match(source_system or ""):
        raise ConnectionError_("source_system inválido (snake_case)")
    configuration = dict(configuration or {})
    desconhecidas = set(configuration) - CONFIG_KEYS[source_type]
    if desconhecidas:
        raise ConnectionError_(f"configuração com chaves não permitidas: {sorted(desconhecidas)}")
    for k, v in configuration.items():
        if _SENSITIVE.search(k) or (isinstance(v, str) and _SENSITIVE.search(v) and len(v) > 24):
            raise ConnectionError_("credenciais não podem ir em configuration — use secret_reference")
    if secret_reference is not None:
        secret_provider.validate_reference(secret_reference)
    if source_type == "FILE":
        if "mapping_id" not in configuration:
            raise ConnectionError_("fonte FILE exige configuration.mapping_id")
        configuration.setdefault("mapping_version", 1)
        load_connection_mapping(configuration)  # valida já no cadastro
    return configuration


def mapping_path(mapping_id: str, version: int) -> Path:
    if not re.match(r"^[a-z][a-z0-9_]{2,60}$", mapping_id or ""):
        raise MappingError("mapping_id inválido")
    return Path(data_platform_dir()) / "mappings" / f"{mapping_id}_v{int(version)}.yaml"


def load_connection_mapping(configuration: dict) -> Mapping:
    p = mapping_path(configuration.get("mapping_id", ""), configuration.get("mapping_version", 1))
    if not p.exists():
        raise MappingError(f"mapping {p.name} não encontrado em data_platform/mappings")
    m = load_mapping_file(p)
    if m.mapping_id != configuration["mapping_id"] or m.version != int(configuration.get("mapping_version", 1)):
        raise MappingError("mapping_id/version do arquivo não conferem com a fonte")
    return m


def validate_connectivity(conn: SourceConnection) -> dict:
    """FILE: mapping válido + RAW gravável. DATABASE/API: ainda não implementado (honesto)."""
    if conn.source_type == "FILE":
        m = load_connection_mapping(conn.configuration or {})
        storage = get_raw_storage()
        ok = storage is not None
        return {"ok": ok, "mapping": m.ref, "entities": [e.source_entity for e in m.entities],
                "detail": "mapping válido e armazenamento RAW disponível"}
    if conn.source_type == "SYNTHETIC":
        return {"ok": True, "detail": "gerador interno"}
    return {"ok": False, "detail": f"conector {conn.source_type} ainda não implementado nesta fase"}


def list_for_tenant(session: Session, tenant_id: str) -> list[SourceConnection]:
    return list(session.execute(select(SourceConnection).where(
        SourceConnection.tenant_id == tenant_id).order_by(SourceConnection.id)).scalars())


def as_dict(c: SourceConnection) -> dict:
    iso = lambda d: d.isoformat() if d else None  # noqa: E731
    return {
        "id": c.id, "tenant_id": c.tenant_id, "name": c.name, "source_type": c.source_type,
        "source_system": c.source_system, "status": c.status,
        "configuration": c.configuration or {},
        "has_secret": c.secret_reference is not None,  # a referência em si não é exibida
        "created_at": iso(c.created_at), "updated_at": iso(c.updated_at),
        "last_run_at": iso(c.last_run_at), "last_success_at": iso(c.last_success_at),
        "last_error_at": iso(c.last_error_at), "last_error_summary": c.last_error_summary,
    }
