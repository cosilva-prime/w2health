"""Cria o bucket do RAW se não existir (deployment com S3-compatível). Idempotente.

    python -m app.ops.storage_init

Só cria o bucket e confirma acesso; política de acesso público fica DESLIGADA (padrão dos
provedores). Versionamento/criptografia/retenção do bucket são configuração de
infraestrutura (docs/OBJECT_STORAGE.md).
"""

from __future__ import annotations

import sys
import time

from app.core.config import get_settings


def main() -> int:
    s = get_settings()
    if s.raw_storage_backend != "s3":
        print("RAW_STORAGE_BACKEND não é s3 — nada a fazer")
        return 0
    from botocore.exceptions import BotoCoreError, ClientError

    from app.data_platform.storage_s3 import S3CompatibleStorage

    st = S3CompatibleStorage.from_settings(s)
    for tentativa in range(30):
        try:
            try:
                st.client.head_bucket(Bucket=st.bucket)
            except ClientError as e:
                if st._code(e) not in ("404", "NoSuchBucket", "NotFound"):
                    raise
                st.client.create_bucket(Bucket=st.bucket)
            st.ping()
            print(f"bucket pronto: {st.bucket}")
            return 0
        except (BotoCoreError, ClientError) as e:
            print(f"aguardando object storage ({tentativa + 1}/30): {type(e).__name__}", file=sys.stderr)
            time.sleep(2)
    return 1


if __name__ == "__main__":
    sys.exit(main())
