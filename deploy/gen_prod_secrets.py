"""Gera deploy/secrets/* para o deployment de REFERÊNCIA (docker-compose.production.example.yml).

    python deploy/gen_prod_secrets.py            # não sobrescreve arquivos existentes

Um arquivo por segredo (nome = campo de configuração), permissões restritas, valores
aleatórios. Em produção real estes arquivos vêm do gerenciador de segredos da nuvem
(montados em /run/secrets) — nunca do repositório. Requer `cryptography` (venv do backend).
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from cryptography.fernet import Fernet

DIR = Path(__file__).resolve().parent / "secrets"


def main() -> None:
    DIR.mkdir(exist_ok=True)
    pg, app, pipe = (secrets.token_urlsafe(24) for _ in range(3))
    host = "db:5432/w2health"
    valores = {
        "postgres_password": pg,
        "app_db_password": app,
        "pipeline_db_password": pipe,
        # papéis distintos: runtime (RLS), dono (migrations), pipeline (RLS, sem DDL)
        "database_url": f"postgresql+psycopg://w2health_app:{app}@{host}",
        "database_admin_url": f"postgresql+psycopg://w2health:{pg}@{host}",
        "database_pipeline_url": f"postgresql+psycopg://w2health_pipeline:{pipe}@{host}",
        "jwt_secret_key": secrets.token_urlsafe(48),
        "data_encryption_key": Fernet.generate_key().decode(),
        "s3_access_key_id": "w2h" + secrets.token_hex(6),
        "s3_secret_access_key": secrets.token_urlsafe(32),
        "metrics_token": secrets.token_urlsafe(32),
    }
    for nome, valor in valores.items():
        p = DIR / nome
        if p.exists():
            print(f"mantido: {nome}")
            continue
        p.write_text(valor, encoding="utf-8")
        os.chmod(p, 0o600)
        print(f"gerado:  {nome}")


if __name__ == "__main__":
    main()
