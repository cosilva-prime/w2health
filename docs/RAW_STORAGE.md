# RAW storage — W2Health (Fase 2)

> **Fase 3:** o protocolo virou `ObjectStorage` (put/get/exists/head/checksum/list/ping) com
> adapter local **e** adapter S3-compatível; a chave é validada por todo adapter em toda
> operação. Detalhe: [OBJECT_STORAGE.md](OBJECT_STORAGE.md).

O PostgreSQL **não** é o data lake. O payload original recebido (bytes exatos do arquivo)
vai para um armazenamento de objetos; o banco guarda só metadados em `raw_objects`.
Código: `backend/app/data_platform/storage.py`.

## 1. Abstração

```python
class RawStorage(Protocol):
    def put(self, key: str, data: bytes) -> RawObjectRef: ...   # recusa sobrescrever
    def get(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def list(self, prefix: str) -> list[str]: ...
    def delete_prefix(self, prefix: str) -> int: ...            # só expurgo LGPD por tenant
```

| Implementação | Estado | Configuração |
|---|---|---|
| `LocalFilesystemRawStorage` | **implementada** (DEV/teste/Compose) | `RAW_STORAGE_BACKEND=local`, `RAW_STORAGE_ROOT` (Compose: volume `rawdata` em `/var/lib/w2health/raw`) |
| `S3CompatibleStorage` (AWS S3, MinIO, Ceph, R2…) | **implementada na Fase 3** — escrita condicional (imutável), sha256 em metadado, erros traduzidos para retry | `RAW_STORAGE_BACKEND=s3`, `S3_*` — ver [OBJECT_STORAGE.md](OBJECT_STORAGE.md) |
| Azure Blob / ADLS, GCS | não implementadas — mesmo protocolo | — |

## 2. Chaves (cloud-agnostic, prefixo por tenant)

```
tenant/<tenant_id>/raw/<source_connection_id>/<source_entity>/<ingestion_run_id>/<arquivo>
ex.: tenant/vida-plena-csv/raw/1/eventos/4/eventos.csv
```

- cada segmento é validado (`^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$`) — `..`, `/`, vazio são
  recusados (`test_raw_key_recusa_path_traversal`);
- o caminho resolvido precisa ficar dentro da raiz (defesa em profundidade);
- prefixo por tenant permite política de acesso/retenção/eliminação por tenant no bucket.

## 3. Imutabilidade

`put` recusa uma chave existente. Correção nunca altera o RAW: um novo envio gera uma nova
ingestão e, portanto, novas chaves. O conteúdo é guardado **byte a byte** (sem
normalização de fim de linha/encoding) — o `sha256` em `raw_objects` confere com o arquivo
original (`test_raw_rastreavel_e_integro`).

## 4. Metadados (`raw_objects`, com RLS)

| Coluna | |
|---|---|
| `tenant_id`, `source_connection_id`, `ingestion_run_id` | vínculo e linhagem |
| `source_entity`, `file_name` | qual arquivo/entidade |
| `storage_key` | onde está (relativo ao backend configurado) |
| `sha256`, `size_bytes`, `records` | integridade e volume |
| `received_at` | quando entrou |

## 5. Segurança

- diretório RAW fora de qualquer pasta servida (não há rota que leia o RAW);
- dado de saúde pseudonimizado na origem é responsabilidade do cliente (ver
  [CLIENT_DATA_REQUIREMENTS.md](CLIENT_DATA_REQUIREMENTS.md)); o RAW **não** deve receber
  nome, CPF ou carteirinha em claro;
- produção: bucket privado, cifragem em repouso (KMS do provedor), versionamento/object
  lock opcional, acesso só pelo papel do pipeline. **Nada disso existe ainda** — é requisito
  de infraestrutura (ver [V1_ROADMAP.md](V1_ROADMAP.md)).

## 6. Backup

O RAW faz parte do backup (é a única cópia do dado original). O teste local empacota o
volume `rawdata` — ver [BACKUP_AND_RECOVERY.md](BACKUP_AND_RECOVERY.md).
