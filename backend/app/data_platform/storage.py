"""RAW storage — abstração de armazenamento do dado ORIGINAL recebido.

O PostgreSQL não é o data lake: o payload original fica num object storage, e o banco
guarda só os metadados (`raw_objects`). Implementações:

* `LocalFilesystemRawStorage` — DEV/teste (diretório fora de qualquer pasta pública);
* adapters futuros (S3 / ADLS / GCS / MinIO) implementam o mesmo protocolo — nenhum outro
  módulo monta caminho físico.

Organização lógica das chaves (cloud-agnostic, prefixo por tenant):

    tenant/<tenant_id>/raw/<source_connection_id>/<source_entity>/<ingestion_run_id>/<arquivo>

Imutabilidade lógica: `put` recusa sobrescrever uma chave existente. Correções nunca
alteram o RAW — uma nova ingestão gera novas chaves.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings

_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$")


class RawStorageError(RuntimeError):
    pass


@dataclass(frozen=True)
class RawObjectRef:
    key: str
    size: int
    sha256: str


def raw_key(tenant_id: str, source_connection_id: int, source_entity: str,
            ingestion_run_id: int, filename: str) -> str:
    partes = ["tenant", tenant_id, "raw", str(source_connection_id), source_entity,
              str(ingestion_run_id), filename]
    for p in partes:
        if not _SEGMENT.match(p) or p in (".", ".."):
            raise RawStorageError("segmento de chave RAW inválido")
    return "/".join(partes)


class RawStorage(Protocol):
    def put(self, key: str, data: bytes) -> RawObjectRef: ...
    def get(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def list(self, prefix: str) -> list[str]: ...
    def delete_prefix(self, prefix: str) -> int: ...


class LocalFilesystemRawStorage:
    """Filesystem local. Escrita atômica (arquivo temporário + rename), sem sobrescrita."""

    def __init__(self, root: str | os.PathLike) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root not in p.parents:
            raise RawStorageError("chave fora da raiz do RAW")
        return p

    def put(self, key: str, data: bytes) -> RawObjectRef:
        p = self._path(key)
        if p.exists():
            raise RawStorageError("objeto RAW já existe (RAW é imutável)")
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".part")
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
        return RawObjectRef(key=key, size=len(data), sha256=hashlib.sha256(data).hexdigest())

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def list(self, prefix: str) -> list[str]:
        base = self._path(prefix) if prefix else self.root
        if not base.exists():
            return []
        return sorted(str(p.relative_to(self.root)).replace("\\", "/")
                      for p in base.rglob("*") if p.is_file())

    def delete_prefix(self, prefix: str) -> int:
        """Somente para expurgo/eliminação controlada por tenant (LGPD) — nunca no pipeline."""
        n = 0
        for k in self.list(prefix):
            self._path(k).unlink()
            n += 1
        return n


_storage: RawStorage | None = None


def get_raw_storage() -> RawStorage:
    global _storage
    if _storage is None:
        s = get_settings()
        if s.raw_storage_backend != "local":
            raise RawStorageError(f"backend de RAW não suportado nesta fase: {s.raw_storage_backend}")
        _storage = LocalFilesystemRawStorage(s.raw_storage_root)
    return _storage


def set_raw_storage(storage: RawStorage | None) -> None:
    """Injeção para testes/adapters."""
    global _storage
    _storage = storage
