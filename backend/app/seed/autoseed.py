"""Popula dados sintéticos automaticamente no primeiro start, se o banco estiver vazio.

Usado pelo entrypoint do container (`scripts/start.sh`) quando `AUTO_SEED=true` — cenário
de ambientes sem acesso a shell para rodar `python -m app.seed.run` manualmente (ex.: Render
free tier). É idempotente: só semeia se `seed_manifest` estiver vazia, então reinícios do
container não recriam nem apagam dados já gerados.
"""

import os

from app.db.session import SessionLocal
from app.models import SeedManifest
from app.seed.config import SeedConfig
from app.seed.run import run_seed


def main() -> None:
    with SessionLocal() as session:
        if session.query(SeedManifest).count() > 0:
            print("[autoseed] dados já existem, pulando seed.", flush=True)
            return
        n_beneficiarios = int(os.environ.get("AUTO_SEED_BENEFICIARIOS", "5000"))
        cfg = SeedConfig(n_beneficiarios=n_beneficiarios)
        print(f"[autoseed] banco vazio — gerando {n_beneficiarios} beneficiários...", flush=True)
        run_seed(cfg, session)


if __name__ == "__main__":
    main()
