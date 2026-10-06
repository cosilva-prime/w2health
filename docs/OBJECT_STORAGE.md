# Object Storage — W2Health (Fase 3)

O RAW (bytes originais recebidos do cliente) vive num object storage; o banco guarda só
metadados (`raw_objects`). Código: `backend/app/data_platform/storage.py` (protocolo +
adapter local) e `storage_s3.py` (adapter S3-compatível). Visão do RAW: [RAW_STORAGE.md](RAW_STORAGE.md).

## 1. Interface (neutra de provedor)

```python
class ObjectStorage(Protocol):
    def put(self, key, data, *, content_type=...) -> RawObjectRef   # recusa sobrescrever
    def get(self, key) -> bytes
    def exists(self, key) -> bool
    def head(self, key) -> ObjectMeta          # tamanho, sha256 (metadado), content-type
    def checksum(self, key) -> str             # sha256 RECALCULADO do conteúdo
    def list(self, prefix) -> list[str]
    def delete_prefix(self, prefix) -> int     # só expurgo controlado (LGPD), nunca no pipeline
    def ping(self) -> None                     # readiness
```

Erros no vocabulário do domínio: `StorageUnavailable` (retentável no worker),
`ObjectNotFound`, `ObjectExists`, `RawStorageError` (definitivos).

## 2. Adapters

| Adapter | Uso | Configuração |
|---|---|---|
| `LocalFilesystemRawStorage` | DEV, testes, piloto em volume persistente | `RAW_STORAGE_BACKEND=local`, `RAW_STORAGE_ROOT`. Em produção exige `RAW_STORAGE_ALLOW_LOCAL_IN_PRODUCTION=true` (decisão explícita) |
| `S3CompatibleStorage` | **AWS S3, MinIO, Ceph RGW, Cloudflare R2** e qualquer API S3 | `RAW_STORAGE_BACKEND=s3`, `S3_BUCKET`, `S3_ENDPOINT_URL` (vazio = AWS), `S3_REGION`, `S3_PREFIX`, `S3_FORCE_PATH_STYLE`, `S3_ACCESS_KEY_ID`/`S3_SECRET_ACCESS_KEY` (ou cadeia padrão do SDK: perfil de instância/workload identity) |
| Azure Blob / ADLS, GCS | **não implementados** — entram como novo adapter do mesmo protocolo | — |

Decisão: a API S3 é o denominador comum (inclui MinIO para on-premises/nuvem privada). Nenhuma
nuvem foi escolhida; o SDK (`boto3`) é importado **só** em `storage_s3.py`
(`test_dominio_nao_importa_sdk_de_nuvem`).

## 3. Garantias

* **Chave validada em toda operação, em todo adapter** (`validate_key`): segmentos
  `[A-Za-z0-9][A-Za-z0-9._-]*`, sem `.`/`..`, sem `/` inicial, sem `\`, sem byte nulo, sem
  segmento vazio. Nome de arquivo enviado não entra na chave (a chave usa a entidade do
  mapping) — `../../tenant/b/eventos.csv` vira `tenant/<a>/raw/.../eventos.csv`.
* **Prefixo por tenant**: `tenant/<id>/raw/<fonte>/<entidade>/<ingestão>/<arquivo>`;
  `tenant_prefix()` termina em `/` (tenant `a` não lista `ab`).
* **Imutabilidade**: local = `O_EXCL` + rename atômico; S3 = `PutObject` com
  `If-None-Match: *` (o servidor recusa sobrescrita, inclusive entre réplicas concorrentes).
* **Integridade**: sha256 calculado na recepção, gravado em `raw_objects` e como metadado
  do objeto; o worker recalcula ao ler (divergência = falha definitiva de integridade).
* **Falha de storage**: na recepção → HTTP 503, ingestão `FAILED`, sem job; no worker →
  retry com backoff.

Testes (`tests/test_object_storage.py`, 46 casos): o mesmo contrato roda contra o adapter
local **e** contra um MinIO real (`S3_TEST_ENDPOINT`); chaves maliciosas; prefixos; tradução
de erros S3 (404, 412, 5xx, conexão) para o domínio.

## 4. Requisitos do bucket em produção (infraestrutura — não configurados pela aplicação)

| Item | Requisito |
|---|---|
| Acesso | bucket privado; bloqueio de acesso público; só os papéis da API e do worker (leitura/escrita no prefixo `tenant/`) |
| Cifragem | em repouso com chave gerenciada (KMS do provedor ou SSE do MinIO) |
| Transporte | HTTPS para o endpoint (no compose de referência o tráfego é interno) |
| Versionamento / object lock | recomendado (proteção contra exclusão acidental/ransomware) |
| Retenção | alinhada ao contrato e à política de eliminação por tenant ([LGPD_TECHNICAL_CONTROLS.md](LGPD_TECHNICAL_CONTROLS.md)) |
| Backup/replicação | replicação para outra zona/região ou backup do bucket ([BACKUP_AND_RECOVERY.md](BACKUP_AND_RECOVERY.md)) |

O bucket é criado por `python -m app.ops.storage_init` (idempotente) no deployment de
referência; políticas acima ficam com a infraestrutura.
