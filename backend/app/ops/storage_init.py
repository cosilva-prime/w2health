"""Cria o bucket do RAW se não existir (deployment com S3-compatível). Idempotente.

    python -m app.ops.storage_init

Só cria o bucket e confirma acesso; acesso público fica DESLIGADO (padrão dos provedores).
Versionamento, criptografia e retenção do bucket são configuração de infraestrutura
(docs/OBJECT_STORAGE.md). O SDK fica confinado ao adapter (`storage_s3.py`).
"""

from __future__ import annotations

import sys
import time

from app.core.config import get_settings
from app.data_platform.storage import StorageUnavailable, build_storage_from_settings


def main() -> int:
    s = get_settings()
    if s.raw_storage_backend != "s3":
        print("RAW_STORAGE_BACKEND não é s3 — nada a fazer")
        return 0
    st = build_storage_from_settings()
    for tentativa in range(30):
        try:
            st.ensure_bucket()
            st.ping()
            print(f"bucket pronto: {st.bucket}")
            return 0
        except StorageUnavailable:
            print(f"aguardando object storage ({tentativa + 1}/30)", file=sys.stderr)
            time.sleep(2)
    return 1


if __name__ == "__main__":
    sys.exit(main())
