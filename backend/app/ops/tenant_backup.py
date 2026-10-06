"""Export / import LÓGICO de um único tenant (restauração por tenant).

    python -m app.ops.tenant_backup export --tenant <id> --out <arquivo.tar.gz> [--sem-raw]
    python -m app.ops.tenant_backup verify --file <arquivo.tar.gz>
    python -m app.ops.tenant_backup import --file <arquivo.tar.gz> --tenant <id> --confirmar <id>

Diferença para o backup físico (docs/BACKUP_AND_RECOVERY.md): o `pg_dump`/PITR restaura o
BANCO INTEIRO (disaster recovery). Para devolver UM tenant ao estado de um ponto anterior
sem tocar nos demais, este módulo exporta só as linhas do tenant (data plane + control plane
do tenant) e o RAW do prefixo `tenant/<id>/`, com manifesto e sha256 por arquivo.

Garantias do import:
* tenant do arquivo == tenant pedido == confirmação digitada (sem import "no tenant errado");
* revisão Alembic do arquivo == revisão do banco (esquema idêntico, sem conversão implícita);
* sha256 de cada tabela confere com o manifesto (arquivo adulterado/corrompido é recusado);
* identidades globais referenciadas (usuários dos vínculos, planos) precisam existir;
* UMA transação: apaga as linhas atuais do tenant e carrega as do arquivo — falhou, nada muda;
* outros tenants não são tocados (todas as operações filtram `tenant_id` e a sessão roda com
  `app.tenant_id` = tenant, valendo o RLS mesmo com papel dono não-superusuário);
* auditoria NUNCA é apagada: linhas de `audit_logs` do arquivo entram só se faltarem;
* sessões/refresh tokens não são exportados (credenciais efêmeras; o import revoga sessões
  ativas do tenant para forçar novo login).

Limites (documentados): ids são preservados — importar em OUTRO banco que já use os mesmos
ids falha por colisão (o procedimento é restaurar no mesmo ambiente ou num banco vazio do
mesmo esquema). Segredos do tenant vão cifrados: o ambiente de destino precisa da mesma
DATA_ENCRYPTION_KEY.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import tarfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

FORMAT_VERSION = 1
_TENANT = re.compile(r"^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$")
#: control plane do tenant exportado (sessões/tokens ficam de fora de propósito)
CONTROL_TENANT_TABLES = (
    "tenant_settings",
    "tenant_branding",
    "tenant_branding_assets",
    "tenant_features",
    "tenant_secrets",
    "tenant_onboarding",
    "user_tenants",
    "pipeline_jobs",
)
#: tabelas carregadas sem apagar (INSERT ... ON CONFLICT DO NOTHING)
APPEND_ONLY = ("audit_logs",)


class TenantBackupError(RuntimeError):
    pass


@dataclass(frozen=True)
class TableSpec:
    name: str
    columns: tuple[str, ...]
    pk: tuple[str, ...]


def _specs() -> tuple[list[TableSpec], list[TableSpec]]:
    import app.models  # noqa: F401
    from app.db.base import Base, ControlBase

    def spec(t) -> TableSpec:
        return TableSpec(
            t.name, tuple(c.name for c in t.columns), tuple(c.name for c in t.primary_key.columns)
        )

    data = [spec(t) for t in Base.metadata.sorted_tables if "tenant_id" in t.c]
    ctrl_by = {t.name: t for t in ControlBase.metadata.sorted_tables}
    control = [spec(ctrl_by[n]) for n in CONTROL_TENANT_TABLES] + [
        spec(ctrl_by[n]) for n in APPEND_ONLY
    ]
    return data, control


def _check_tenant(tenant_id: str) -> str:
    if not _TENANT.match(tenant_id or ""):
        raise TenantBackupError("tenant inválido")
    return tenant_id


def _cols(spec: TableSpec) -> str:
    return ", ".join(f'"{c}"' for c in spec.columns)


def _copy_out(raw, sql: str) -> bytes:
    buf = io.BytesIO()
    with raw.cursor() as cur, cur.copy(sql) as cp:
        for chunk in cp:
            buf.write(chunk)
    return buf.getvalue()


def _copy_in(raw, sql: str, data: bytes) -> None:
    with raw.cursor() as cur, cur.copy(sql) as cp:
        cp.write(data)


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _revision(conn) -> str:
    if conn.execute(text("SELECT to_regclass('alembic_version')")).scalar() is None:
        return "sem-alembic"  # banco criado por create_all (testes)
    return conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none() or "?"


# ============================================================================ export
def export_tenant(
    engine: Engine, tenant_id: str, out: Path, *, include_raw: bool = True, storage=None
) -> dict:
    tenant_id = _check_tenant(tenant_id)
    data, control = _specs()
    arquivos: dict[str, bytes] = {}
    tabelas = []
    with engine.connect() as conn, conn.begin():
        conn.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": tenant_id})
        if (
            conn.execute(text("SELECT 1 FROM tenants WHERE id = :t"), {"t": tenant_id}).first()
            is None
        ):
            raise TenantBackupError("tenant inexistente")
        revision = _revision(conn)
        raw = conn.connection.dbapi_connection
        lit = "'" + tenant_id + "'"  # validado por regex acima
        from app.models import Tenant

        tcols = ", ".join(f'"{c.name}"' for c in Tenant.__table__.columns)
        blocos = [("tenants", f"SELECT {tcols} FROM tenants WHERE id = {lit}")]
        blocos += [
            (s.name, f"SELECT {_cols(s)} FROM {s.name} WHERE tenant_id = {lit} ORDER BY 1")
            for s in data + control
        ]
        blocos.append(("competencias", "SELECT * FROM competencias ORDER BY 1"))
        for nome, sql in blocos:
            b = _copy_out(raw, f"COPY ({sql}) TO STDOUT WITH (FORMAT csv, HEADER)")
            arquivos[f"tables/{nome}.csv"] = b
            tabelas.append(
                {"name": nome, "rows": max(b.count(b"\n") - 1, 0), "sha256": _sha(b)}
            )
    raw_objs = []
    if include_raw:
        from app.data_platform.storage import get_raw_storage, tenant_prefix

        st = storage or get_raw_storage()
        for key in st.list(tenant_prefix(tenant_id)):
            b = st.get(key)
            arquivos[f"raw/{key}"] = b
            raw_objs.append({"key": key, "sha256": _sha(b), "size": len(b)})
    manifest = {
        "format_version": FORMAT_VERSION,
        "tenant_id": tenant_id,
        "alembic_revision": revision,
        "created_at": datetime.now(UTC).isoformat(),
        "tables": tabelas,
        "raw_objects": raw_objs,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(out, "w:gz") as tar:
        for nome, b in [
            ("manifest.json", json.dumps(manifest, indent=2).encode()),
            *arquivos.items(),
        ]:
            info = tarfile.TarInfo(nome)
            info.size, info.mtime, info.mode = len(b), 0, 0o600
            tar.addfile(info, io.BytesIO(b))
    return manifest


# ============================================================================ leitura / verificação
def read_archive(path: Path) -> tuple[dict, dict[str, bytes]]:
    files: dict[str, bytes] = {}
    with tarfile.open(path, "r:gz") as tar:
        for m in tar.getmembers():
            if not m.isfile() or m.name.startswith("/") or ".." in m.name.split("/"):
                raise TenantBackupError("arquivo de backup com caminho inválido")
            files[m.name] = tar.extractfile(m).read()
    if "manifest.json" not in files:
        raise TenantBackupError("manifest.json ausente")
    manifest = json.loads(files.pop("manifest.json"))
    if manifest.get("format_version") != FORMAT_VERSION:
        raise TenantBackupError("versão de formato não suportada")
    for t in manifest["tables"]:
        b = files.get(f"tables/{t['name']}.csv")
        if b is None or _sha(b) != t["sha256"]:
            raise TenantBackupError(
                f"tabela {t['name']} ausente ou adulterada (sha256 não confere)"
            )
    for r in manifest["raw_objects"]:
        b = files.get(f"raw/{r['key']}")
        if b is None or _sha(b) != r["sha256"]:
            raise TenantBackupError("objeto RAW ausente ou adulterado (sha256 não confere)")
    return manifest, files


# ============================================================================ import
def import_tenant(
    engine: Engine, path: Path, tenant_id: str, *, confirm: str, storage=None
) -> dict:
    tenant_id = _check_tenant(tenant_id)
    if confirm != tenant_id:
        raise TenantBackupError("confirmação não confere com o tenant")
    manifest, files = read_archive(path)
    if manifest["tenant_id"] != tenant_id:
        raise TenantBackupError("o arquivo é de outro tenant")
    data, control = _specs()
    contagens = {}
    with engine.connect() as conn:  # noqa: SIM117 — transação explícita dentro da conexão
        with conn.begin():
            conn.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": tenant_id})
            if _revision(conn) != manifest["alembic_revision"]:
                raise TenantBackupError(
                    f"esquema diferente: arquivo {manifest['alembic_revision']} × "
                    f"banco {_revision(conn)}"
                )
            raw = conn.connection.dbapi_connection
            lit = "'" + tenant_id + "'"
            _ensure_globals(conn, files)
            _somente_este_tenant(files, data + control, tenant_id)
            # 1. tenant (upsert — sessões e vínculos apontam para ele) + calendário global
            _upsert(raw, "tenants", files["tables/tenants.csv"], ("id",), update=True)
            _upsert(raw, "competencias", files["tables/competencias.csv"], None, update=False)
            # 2. apaga o estado atual do tenant (ordem inversa de dependência), nunca a auditoria
            for s in reversed(control[: len(CONTROL_TENANT_TABLES)]):
                conn.exec_driver_sql(f"DELETE FROM {s.name} WHERE tenant_id = {lit}")
            for s in reversed(data):
                conn.exec_driver_sql(f"DELETE FROM {s.name} WHERE tenant_id = {lit}")
            # 3. carrega na ordem de dependência
            for s in data + control[: len(CONTROL_TENANT_TABLES)]:
                b = files[f"tables/{s.name}.csv"]
                if _linhas(b):
                    _copy_in(
                        raw, f"COPY {s.name} ({_cols(s)}) FROM STDIN WITH (FORMAT csv, HEADER)", b
                    )
                contagens[s.name] = _linhas(b)
            for s in control[len(CONTROL_TENANT_TABLES) :]:
                _upsert(raw, s.name, files[f"tables/{s.name}.csv"], s.pk, update=False)
            # 4. sequências e sessões
            for s in data + control:
                _ajusta_sequencia(conn, s)
            conn.execute(
                text(
                    "UPDATE auth_sessions SET revoked_at = now() WHERE tenant_id = :t "
                    "AND revoked_at IS NULL"
                ),
                {"t": tenant_id},
            )
    raw_restaurados = 0
    if manifest["raw_objects"]:
        from app.data_platform.storage import ObjectExists, get_raw_storage

        st = storage or get_raw_storage()
        for r in manifest["raw_objects"]:
            if not r["key"].startswith(f"tenant/{tenant_id}/"):
                raise TenantBackupError("objeto RAW fora do prefixo do tenant")
            try:
                st.put(r["key"], files[f"raw/{r['key']}"])
                raw_restaurados += 1
            except ObjectExists:
                if st.checksum(r["key"]) != r["sha256"]:
                    raise TenantBackupError(f"RAW divergente no destino: {r['key']}") from None
    return {
        "tenant_id": tenant_id,
        "tabelas": contagens,
        "raw_restaurados": raw_restaurados,
        "alembic_revision": manifest["alembic_revision"],
    }


def _somente_este_tenant(files: dict[str, bytes], specs: list[TableSpec], tenant_id: str) -> None:
    """Antes de carregar: toda linha de toda tabela precisa ser do tenant pedido."""
    import csv

    for s in specs:
        for row in csv.DictReader(io.StringIO(files[f"tables/{s.name}.csv"].decode())):
            if row.get("tenant_id") != tenant_id:
                raise TenantBackupError(f"linha de outro tenant no arquivo ({s.name})")
    for row in csv.DictReader(io.StringIO(files["tables/tenants.csv"].decode())):
        if row.get("id") != tenant_id:
            raise TenantBackupError("cadastro de outro tenant no arquivo")


def _linhas(b: bytes) -> int:
    return max(b.count(b"\n") - 1, 0)


def _ensure_globals(conn, files: dict[str, bytes]) -> None:
    """Usuários dos vínculos e o plano do tenant precisam existir no destino."""
    import csv

    vinc = list(csv.DictReader(io.StringIO(files["tables/user_tenants.csv"].decode())))
    ids = {v["user_id"] for v in vinc}
    if ids:
        existentes = {
            str(r[0])
            for r in conn.execute(
                text("SELECT id FROM users WHERE id = ANY(CAST(:i AS uuid[]))"), {"i": list(ids)}
            )
        }
        faltam = ids - existentes
        if faltam:
            raise TenantBackupError(f"{len(faltam)} usuário(s) dos vínculos não existem no destino")
    t = next(csv.DictReader(io.StringIO(files["tables/tenants.csv"].decode())))
    if (
        t.get("plan_id")
        and conn.execute(
            text("SELECT 1 FROM plans WHERE id = :p"), {"p": int(t["plan_id"])}
        ).first()
        is None
    ):
        raise TenantBackupError("plano do tenant não existe no destino")


def _upsert(raw, table: str, data: bytes, pk: tuple[str, ...] | None, *, update: bool) -> None:
    header = data.split(b"\n", 1)[0].decode().strip()
    cols = [c.strip('"') for c in header.split(",")]
    tmp = f"_w2h_imp_{table}"
    with raw.cursor() as cur:
        cur.execute(f"CREATE TEMP TABLE {tmp} (LIKE {table} INCLUDING DEFAULTS) ON COMMIT DROP")
    if _linhas(data):
        _copy_in(raw, f"COPY {tmp} ({', '.join(cols)}) FROM STDIN WITH (FORMAT csv, HEADER)", data)
    collist = ", ".join(cols)
    if pk is None:
        conflito = "ON CONFLICT DO NOTHING"
    elif update:
        sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in pk)
        conflito = f"ON CONFLICT ({', '.join(pk)}) DO UPDATE SET {sets}"
    else:
        conflito = f"ON CONFLICT ({', '.join(pk)}) DO NOTHING"
    with raw.cursor() as cur:
        cur.execute(f"INSERT INTO {table} ({collist}) SELECT {collist} FROM {tmp} {conflito}")


def _ajusta_sequencia(conn, s: TableSpec) -> None:
    if len(s.pk) != 1:
        return
    seq = conn.execute(
        text("SELECT pg_get_serial_sequence(:t, :c)"), {"t": s.name, "c": s.pk[0]}
    ).scalar()
    if seq:
        conn.execute(
            text(
                f"SELECT setval(:s, GREATEST("
                f"(SELECT coalesce(max({s.pk[0]}), 0) FROM {s.name}), 1))"
            ),
            {"s": seq},
        )


# ============================================================================ CLI
def main(argv: list[str] | None = None) -> int:
    from app.core.config import get_settings
    from app.db.session import get_admin_engine

    ap = argparse.ArgumentParser(prog="tenant_backup")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--tenant", required=True)
    e.add_argument("--out", required=True)
    e.add_argument("--sem-raw", action="store_true")
    v = sub.add_parser("verify")
    v.add_argument("--file", required=True)
    i = sub.add_parser("import")
    i.add_argument("--file", required=True)
    i.add_argument("--tenant", required=True)
    i.add_argument(
        "--confirmar", required=True, help="repita o id do tenant (proteção contra engano)"
    )
    a = ap.parse_args(argv)
    get_settings()
    try:
        if a.cmd == "export":
            m = export_tenant(get_admin_engine(), a.tenant, Path(a.out), include_raw=not a.sem_raw)
            print(
                json.dumps(
                    {
                        "arquivo": a.out,
                        "tabelas": len(m["tables"]),
                        "raw": len(m["raw_objects"]),
                        "revisao": m["alembic_revision"],
                    },
                    ensure_ascii=False,
                )
            )
        elif a.cmd == "verify":
            m, _ = read_archive(Path(a.file))
            print(
                json.dumps(
                    {
                        "ok": True,
                        "tenant": m["tenant_id"],
                        "revisao": m["alembic_revision"],
                        "linhas": sum(t["rows"] for t in m["tables"]),
                    },
                    ensure_ascii=False,
                )
            )
        else:
            r = import_tenant(get_admin_engine(), Path(a.file), a.tenant, confirm=a.confirmar)
            print(json.dumps(r, ensure_ascii=False))
    except TenantBackupError as ex:
        print(f"erro: {ex}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
