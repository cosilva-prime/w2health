"""Object Storage do RAW — abstração neutra de provedor.

O PostgreSQL não é o data lake: o payload original fica num object storage e o banco guarda
só os metadados (`raw_objects`). O domínio (pipeline, worker, backup) conhece APENAS o
protocolo `ObjectStorage` abaixo — nenhum SDK de nuvem é importado fora do adapter.

Implementações:

* `LocalFilesystemRawStorage` — DEV/teste/piloto em volume (filesystem);
* `S3CompatibleStorage` (`storage_s3.py`) — qualquer API S3 (AWS S3, MinIO, Ceph, R2…).
  Azure Blob/ADLS ou GCS entram como outro adapter do mesmo protocolo.

Chaves (cloud-agnostic, prefixo por tenant):

    tenant/<tenant_id>/raw/<source_connection_id>/<source_entity>/<ingestion_run_id>/<arquivo>

`validate_key` é aplicada por TODO adapter em toda operação: segmentos com caracteres
restritos, sem `.`/`..`, sem barra inicial, sem vazio — um tenant não consegue montar uma
chave que caia no prefixo de outro, e nome de arquivo malicioso não vira caminho.

Imutabilidade lógica: `put` recusa sobrescrever (S3: escrita condicional `If-None-Match`).

Erros (usados pela política de retry do worker — docs/WORKER_AND_QUEUE.md):
* `StorageUnavailable` — indisponibilidade/transiente → **retentável**;
* `ObjectNotFound`, `ObjectExists`, `RawStorageError` (chave inválida, integridade) → definitivos.
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
    """Erro definitivo de storage (chave inválida, integridade, uso incorreto)."""


class StorageUnavailable(RawStorageError):
    """Storage indisponível ou falha transitória — a operação pode ser repetida."""


class ObjectNotFound(RawStorageError):
    pass


class ObjectExists(RawStorageError):
    pass


@dataclass(frozen=True)
class RawObjectRef:
    key: str
    size: int
    sha256: str


@dataclass(frozen=True)
class ObjectMeta:
    key: str
    size: int
    sha256: str | None
    content_type: str | None


def validate_key(key: str, *, allow_prefix: bool = False) -> str:
    """Valida uma chave (ou prefixo terminado em '/') — defesa comum a todos os adapters."""
    if not isinstance(key, str) or not key or key.startswith("/") or "\\" in key or "\x00" in key:
        raise RawStorageError("chave de objeto inválida")
    corpo = key[:-1] if (allow_prefix and key.endswith("/")) else key
    for seg in corpo.split("/"):
        if not _SEGMENT.match(seg) or seg in (".", ".."):
            raise RawStorageError("chave de objeto inválida")
    return key


def raw_key(tenant_id: str, source_connection_id: int, source_entity: str,
            ingestion_run_id: int, filename: str) -> str:
    partes = ["tenant", tenant_id, "raw", str(source_connection_id), source_entity,
              str(ingestion_run_id), filename]
    for p in partes:
        if not _SEGMENT.match(p) or p in (".", ".."):
            raise RawStorageError("segmento de chave RAW inválido")
    return validate_key("/".join(partes))


def tenant_prefix(tenant_id: str) -> str:
    if not _SEGMENT.match(tenant_id or ""):
        raise RawStorageError("tenant inválido para prefixo")
    return f"tenant/{tenant_id}/"


class ObjectStorage(Protocol):
    backend: str

    def put(self, key: str, data: bytes, *, content_type: str = "application/octet-stream") -> RawObjectRef: ...
    def get(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def head(self, key: str) -> ObjectMeta: ...
    def checksum(self, key: str) -> str: ...
    def list(self, prefix: str) -> list[str]: ...
    def delete_prefix(self, prefix: str) -> int: ...
    def ping(self) -> None: ...


#: nome histórico (Fase 2) — mesmo protocolo
RawStorage = ObjectStorage


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class LocalFilesystemRawStorage:
    """Filesystem local. Escrita atômica (arquivo temporário + rename), sem sobrescrita."""

    backend = "local"

    def __init__(self, root: str | os.PathLike) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str, *, prefix: bool = False) -> Path:
        validate_key(key, allow_prefix=prefix)
        p = (self.root / key).resolve()
        if self.root not in p.parents and p != self.root:
            raise RawStorageError("chave fora da raiz do RAW")
        return p

    def put(self, key: str, data: bytes, *, content_type: str = "application/octet-stream") -> RawObjectRef:
        p = self._path(key)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            # O_EXCL: falha se o arquivo já existe — imutabilidade sem condição de corrida
            fd = os.open(str(p) + ".part", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
        except FileExistsError as e:
            raise ObjectExists("objeto RAW em gravação concorrente") from e
        except OSError as e:
            raise StorageUnavailable("armazenamento RAW indisponível") from e
        tmp = str(p) + ".part"
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            if p.exists():
                raise ObjectExists("objeto RAW já existe (RAW é imutável)")
            os.replace(tmp, p)
        except ObjectExists:
            Path(tmp).unlink(missing_ok=True)
            raise
        except OSError as e:
            Path(tmp).unlink(missing_ok=True)
            raise StorageUnavailable("armazenamento RAW indisponível") from e
        return RawObjectRef(key=key, size=len(data), sha256=sha256_hex(data))

    def get(self, key: str) -> bytes:
        p = self._path(key)
        try:
            return p.read_bytes()
        except FileNotFoundError as e:
            raise ObjectNotFound("objeto RAW não encontrado") from e
        except OSError as e:
            raise StorageUnavailable("armazenamento RAW indisponível") from e

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def head(self, key: str) -> ObjectMeta:
        p = self._path(key)
        if not p.exists():
            raise ObjectNotFound("objeto RAW não encontrado")
        return ObjectMeta(key=key, size=p.stat().st_size, sha256=None, content_type=None)

    def checksum(self, key: str) -> str:
        return sha256_hex(self.get(key))

    def list(self, prefix: str) -> list[str]:
        base = self._path(prefix, prefix=True) if prefix else self.root
        if not base.exists():
            return []
        return sorted(str(p.relative_to(self.root)).replace("\\", "/")
                      for p in base.rglob("*") if p.is_file() and not p.name.endswith(".part"))

    def delete_prefix(self, prefix: str) -> int:
        """Somente para expurgo/eliminação controlada por tenant (LGPD) — nunca no pipeline."""
        n = 0
        for k in self.list(prefix):
            self._path(k).unlink()
            n += 1
        return n

    def ping(self) -> None:
        if not self.root.is_dir() or not os.access(self.root, os.W_OK):
            raise StorageUnavailable("diretório RAW indisponível")


_storage: ObjectStorage | None = None


def build_storage_from_settings() -> ObjectStorage:
    s = get_settings()
    if s.raw_storage_backend == "local":
        return LocalFilesystemRawStorage(s.raw_storage_root)
    if s.raw_storage_backend == "s3":
        from app.data_platform.storage_s3 import S3CompatibleStorage

        return S3CompatibleStorage.from_settings(s)
    raise RawStorageError(f"backend de RAW desconhecido: {s.raw_storage_backend}")


def get_raw_storage() -> ObjectStorage:
    global _storage
    if _storage is None:
        _storage = build_storage_from_settings()
    return _storage


def set_raw_storage(storage: ObjectStorage | None) -> None:
    """Injeção para testes/adapters."""
    global _storage
    _storage = storage
