"""Adapter S3-compatível do `ObjectStorage` (AWS S3, MinIO, Ceph RGW, Cloudflare R2…).

Único módulo que importa o SDK (boto3). Escolha deliberadamente neutra: a API S3 é o
denominador comum de object storage; Azure Blob/ADLS e GCS entram como OUTRO adapter do
mesmo protocolo, sem tocar no domínio.

Garantias:
* chave validada por `validate_key` antes de qualquer chamada;
* imutabilidade: `PutObject` com `IfNoneMatch="*"` (escrita condicional) — o servidor recusa
  sobrescrever; sem condição de corrida entre réplicas;
* integridade: sha256 calculado no cliente e gravado como metadado (`x-amz-meta-sha256`)
  e como `ChecksumSHA256` verificado pelo servidor quando suportado;
* prefixo opcional (`S3_PREFIX`) para compartilhar bucket entre ambientes;
* credenciais: chaves explícitas (vindas do SecretProvider/variáveis) OU cadeia padrão do
  SDK (perfil de instância/IRSA) — nada é logado;
* falhas de rede/5xx/throttling → `StorageUnavailable` (retentável no worker).
"""

from __future__ import annotations

import base64
import hashlib

from app.data_platform.storage import (
    ObjectExists,
    ObjectMeta,
    ObjectNotFound,
    RawObjectRef,
    RawStorageError,
    StorageUnavailable,
    validate_key,
)

_NOT_FOUND = {"404", "NoSuchKey", "NotFound"}
_EXISTS = {"412", "PreconditionFailed", "ConditionalRequestConflict"}


class S3CompatibleStorage:
    backend = "s3"

    def __init__(self, client, bucket: str, prefix: str = "") -> None:
        if not bucket:
            raise RawStorageError("S3_BUCKET não configurado")
        if prefix:
            validate_key(prefix if prefix.endswith("/") else prefix + "/", allow_prefix=True)
        self.client = client
        self.bucket = bucket
        self.prefix = (prefix.rstrip("/") + "/") if prefix else ""

    @classmethod
    def from_settings(cls, s) -> S3CompatibleStorage:
        import boto3
        from botocore.config import Config

        kwargs = {
            "endpoint_url": s.s3_endpoint_url or None,
            "region_name": s.s3_region or None,
            "config": Config(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "standard"},
                connect_timeout=5,
                read_timeout=60,
                s3={"addressing_style": "path" if s.s3_force_path_style else "auto"},
            ),
        }
        if s.s3_access_key_id and s.s3_secret_access_key:
            kwargs["aws_access_key_id"] = s.s3_access_key_id.get_secret_value()
            kwargs["aws_secret_access_key"] = s.s3_secret_access_key.get_secret_value()
        return cls(boto3.client("s3", **kwargs), s.s3_bucket or "", s.s3_prefix or "")

    # ------------------------------------------------------------------ internos
    def _k(self, key: str, *, prefix: bool = False) -> str:
        validate_key(key, allow_prefix=prefix)
        return self.prefix + key

    @staticmethod
    def _code(e) -> str:
        return str(getattr(e, "response", {}).get("Error", {}).get("Code", ""))

    def _map(self, e: Exception) -> Exception:
        from botocore.exceptions import BotoCoreError, ClientError

        if isinstance(e, ClientError):
            code = self._code(e)
            status = str(e.response.get("ResponseMetadata", {}).get("HTTPStatusCode", ""))
            if code in _NOT_FOUND or status == "404":
                return ObjectNotFound("objeto não encontrado")
            if code in _EXISTS or status == "412":
                return ObjectExists("objeto já existe (RAW é imutável)")
            if status.startswith("5") or code in {
                "SlowDown",
                "RequestTimeout",
                "InternalError",
                "ServiceUnavailable",
            }:
                return StorageUnavailable("object storage indisponível")
            return RawStorageError(f"object storage recusou a operação ({code or status})")
        if isinstance(e, BotoCoreError):  # conexão, timeout, endpoint
            return StorageUnavailable("object storage indisponível")
        return e

    # ------------------------------------------------------------------ protocolo
    def put(
        self, key: str, data: bytes, *, content_type: str = "application/octet-stream"
    ) -> RawObjectRef:
        full = self._k(key)
        digest = hashlib.sha256(data).digest()
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=full,
                Body=data,
                ContentType=content_type,
                IfNoneMatch="*",
                ChecksumSHA256=base64.b64encode(digest).decode(),
                Metadata={"sha256": digest.hex()},
            )
        except Exception as e:  # noqa: BLE001 — traduzido para o vocabulário do domínio
            raise self._map(e) from e
        return RawObjectRef(key=key, size=len(data), sha256=digest.hex())

    def get(self, key: str) -> bytes:
        try:
            return self.client.get_object(Bucket=self.bucket, Key=self._k(key))["Body"].read()
        except Exception as e:  # noqa: BLE001
            raise self._map(e) from e

    def head(self, key: str) -> ObjectMeta:
        try:
            r = self.client.head_object(Bucket=self.bucket, Key=self._k(key))
        except Exception as e:  # noqa: BLE001
            raise self._map(e) from e
        return ObjectMeta(
            key=key,
            size=int(r.get("ContentLength", 0)),
            sha256=(r.get("Metadata") or {}).get("sha256"),
            content_type=r.get("ContentType"),
        )

    def exists(self, key: str) -> bool:
        try:
            self.head(key)
            return True
        except ObjectNotFound:
            return False

    def checksum(self, key: str) -> str:
        """sha256 do CONTEÚDO (recalculado — não confia só no metadado gravado)."""
        return hashlib.sha256(self.get(key)).hexdigest()

    def list(self, prefix: str) -> list[str]:
        full = self._k(prefix, prefix=True) if prefix else self.prefix
        out: list[str] = []
        try:
            for page in self.client.get_paginator("list_objects_v2").paginate(
                Bucket=self.bucket, Prefix=full
            ):
                out += [o["Key"][len(self.prefix) :] for o in page.get("Contents", [])]
        except Exception as e:  # noqa: BLE001
            raise self._map(e) from e
        return sorted(out)

    def delete_prefix(self, prefix: str) -> int:
        """Somente expurgo/eliminação controlada por tenant (LGPD) — nunca no pipeline."""
        chaves = self.list(prefix)
        for i in range(0, len(chaves), 1000):
            lote = [{"Key": self.prefix + k} for k in chaves[i : i + 1000]]
            try:
                self.client.delete_objects(
                    Bucket=self.bucket, Delete={"Objects": lote, "Quiet": True}
                )
            except Exception as e:  # noqa: BLE001
                raise self._map(e) from e
        return len(chaves)

    def ping(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception as e:  # noqa: BLE001
            mapped = self._map(e)
            raise (
                mapped
                if isinstance(mapped, StorageUnavailable)
                else StorageUnavailable("bucket inacessível")
            ) from e
