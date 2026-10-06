"""Fase 3 — Object Storage: o MESMO contrato verificado no adapter local e no adapter S3.

O adapter S3 roda contra um endpoint S3-compatível real quando `S3_TEST_ENDPOINT` está
definido (CI/local: MinIO em contêiner). Sem endpoint, os casos S3 são pulados — os de
mapeamento de erro usam um cliente falso e rodam sempre.
"""

from __future__ import annotations

import os
import uuid

import pytest

from app.data_platform.storage import (
    LocalFilesystemRawStorage,
    ObjectExists,
    ObjectNotFound,
    RawStorageError,
    StorageUnavailable,
    raw_key,
    sha256_hex,
    tenant_prefix,
    validate_key,
)

MALICIOSAS = ["../tenant/b/raw/x", "tenant/a/../b/raw/x", "/tenant/a/raw/x", "tenant/a//raw/x",
              "tenant\\a\\raw", "tenant/a/raw/..", "tenant/a/raw/.", "tenant/a/\x00/x", "",
              "tenant/a/raw/arquivo com espaço.csv", "tenant/a/raw/%2e%2e"]


def _s3():
    endpoint = os.environ.get("S3_TEST_ENDPOINT")
    if not endpoint:
        pytest.skip("S3_TEST_ENDPOINT não definido — adapter S3 não exercitado neste ambiente")
    import boto3
    from botocore.config import Config

    from app.data_platform.storage_s3 import S3CompatibleStorage

    cli = boto3.client("s3", endpoint_url=endpoint, region_name="us-east-1",
                       aws_access_key_id=os.environ.get("S3_TEST_KEY", "w2htest"),
                       aws_secret_access_key=os.environ.get("S3_TEST_SECRET", "w2htest-secret-123"),
                       config=Config(signature_version="s3v4", s3={"addressing_style": "path"}))
    bucket = f"w2h-test-{uuid.uuid4().hex[:8]}"
    cli.create_bucket(Bucket=bucket)
    return S3CompatibleStorage(cli, bucket, prefix="ambiente-teste")


@pytest.fixture(params=["local", "s3"])
def storage(request, tmp_path):
    if request.param == "local":
        return LocalFilesystemRawStorage(tmp_path / "raw")
    return _s3()


# ===================================================================== contrato comum
def test_put_get_head_checksum_list(storage):
    k = raw_key("tenant-a", 1, "eventos", 10, "eventos.csv")
    dados = "id;valor\n1;10,5\n".encode()
    ref = storage.put(k, dados, content_type="text/csv")
    assert ref.sha256 == sha256_hex(dados) and ref.size == len(dados)
    assert storage.get(k) == dados and storage.exists(k)
    assert storage.head(k).size == len(dados)
    assert storage.checksum(k) == sha256_hex(dados)
    assert storage.list(tenant_prefix("tenant-a")) == [k]
    storage.ping()


def test_raw_e_imutavel(storage):
    k = raw_key("tenant-a", 1, "planos", 11, "planos.csv")
    storage.put(k, b"a;b\n1;2\n")
    with pytest.raises(ObjectExists):
        storage.put(k, b"conteudo-trocado")
    assert storage.get(k) == b"a;b\n1;2\n"


def test_objeto_inexistente_e_definitivo(storage):
    with pytest.raises(ObjectNotFound):
        storage.get(raw_key("tenant-a", 1, "eventos", 999, "eventos.csv"))
    assert not storage.exists(raw_key("tenant-a", 1, "eventos", 999, "eventos.csv"))


@pytest.mark.parametrize("chave", MALICIOSAS)
def test_chave_maliciosa_recusada_em_todas_as_operacoes(storage, chave):
    for op in (lambda: storage.put(chave, b"x"), lambda: storage.get(chave),
               lambda: storage.exists(chave), lambda: storage.head(chave)):
        with pytest.raises(RawStorageError):
            op()


def test_prefixo_de_um_tenant_nao_alcanca_outro(storage):
    ka = raw_key("tenant-a", 1, "eventos", 1, "eventos.csv")
    kb = raw_key("tenant-b", 1, "eventos", 1, "eventos.csv")
    storage.put(ka, b"A")
    storage.put(kb, b"B")
    assert storage.list(tenant_prefix("tenant-a")) == [ka]
    assert storage.list(tenant_prefix("tenant-b")) == [kb]
    # "tenant-a" não é prefixo textual de "tenant-ab": a barra final delimita
    storage.put(raw_key("tenant-ab", 1, "eventos", 1, "eventos.csv"), b"AB")
    assert storage.list(tenant_prefix("tenant-a")) == [ka]


@pytest.mark.parametrize("seg", ["..", ".", "a/b", "", "x" * 200, "tenant\\b", "nome;rm -rf"])
def test_raw_key_recusa_segmentos_maliciosos(seg):
    with pytest.raises(RawStorageError):
        raw_key(seg, 1, "eventos", 1, "eventos.csv")
    with pytest.raises(RawStorageError):
        raw_key("tenant-a", 1, seg, 1, "eventos.csv")
    with pytest.raises(RawStorageError):
        raw_key("tenant-a", 1, "eventos", 1, seg)


def test_validate_key_aceita_somente_o_formato_esperado():
    assert validate_key("tenant/a/raw/1/eventos/2/eventos.csv")
    assert validate_key("tenant/a/", allow_prefix=True)
    with pytest.raises(RawStorageError):
        validate_key("tenant/a/")


# ===================================================================== erros → política de retry
class _ClienteFalho:
    def __init__(self, exc):
        self.exc = exc

    def __getattr__(self, _nome):
        def falha(**_kw):
            raise self.exc
        return falha


def _client_error(code: str, status: int):
    from botocore.exceptions import ClientError

    return ClientError({"Error": {"Code": code, "Message": "x"},
                        "ResponseMetadata": {"HTTPStatusCode": status}}, "PutObject")


@pytest.mark.parametrize("exc_factory,esperado", [
    (lambda: _client_error("NoSuchKey", 404), ObjectNotFound),
    (lambda: _client_error("PreconditionFailed", 412), ObjectExists),
    (lambda: _client_error("SlowDown", 503), StorageUnavailable),
    (lambda: _client_error("InternalError", 500), StorageUnavailable),
    (lambda: _client_error("AccessDenied", 403), RawStorageError),
])
def test_s3_traduz_erros_para_o_vocabulario_do_dominio(exc_factory, esperado):
    from app.data_platform.storage_s3 import S3CompatibleStorage

    st = S3CompatibleStorage(_ClienteFalho(exc_factory()), "bucket")
    with pytest.raises(esperado):
        st.put(raw_key("tenant-a", 1, "eventos", 1, "eventos.csv"), b"x")


def test_s3_endpoint_fora_do_ar_e_retentavel():
    from botocore.exceptions import EndpointConnectionError

    from app.data_platform.storage_s3 import S3CompatibleStorage

    st = S3CompatibleStorage(_ClienteFalho(EndpointConnectionError(endpoint_url="http://x")), "bucket")
    with pytest.raises(StorageUnavailable):
        st.get(raw_key("tenant-a", 1, "eventos", 1, "eventos.csv"))
    with pytest.raises(StorageUnavailable):
        st.ping()


def test_s3_sem_bucket_nao_inicializa():
    from app.data_platform.storage_s3 import S3CompatibleStorage

    with pytest.raises(RawStorageError):
        S3CompatibleStorage(object(), "")


def test_dominio_nao_importa_sdk_de_nuvem():
    """O SDK fica confinado ao adapter: pipeline, worker e API não dependem dele."""
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[1] / "app"
    for py in raiz.rglob("*.py"):
        if py.name == "storage_s3.py":
            continue
        txt = py.read_text(encoding="utf-8")
        assert "import boto3" not in txt and "botocore" not in txt, py.name
