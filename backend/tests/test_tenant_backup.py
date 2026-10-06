"""Fase 3 — restauração LÓGICA de um tenant (export/import), sem tocar nos demais."""

from __future__ import annotations

import importlib.util
import io
import json
import tarfile
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import text

from app.data_platform.paths import data_platform_dir
from app.data_platform.storage import get_raw_storage, tenant_prefix
from app.ops.tenant_backup import TenantBackupError, export_tenant, import_tenant, read_archive
from tests.conftest import (
    SUPERADMIN_EMAIL,
    TENANT_A,
    create_tenant,
    create_user,
    iso_client,
    upload_and_wait,
)

pytestmark = pytest.mark.scenarios
BK = "bk-a"

#: assinatura do estado do tenant: contagens + somas de controle por tabela
_ASSINATURA = {
    "eventos_assistenciais": "count(*), sum(valor_apresentado), sum(valor_pago), string_agg(source_record_id, ',' ORDER BY id)",
    "beneficiarios": "count(*), string_agg(codigo || coalesce(data_saida::text, ''), ',' ORDER BY id)",
    "receitas": "count(*), sum(receita_contraprestacao)",
    "agg_sinistralidade_competencia": "count(*), sum(despesa_liquida), sum(receita)",
    "ingestion_runs": "count(*), string_agg(status || coalesce(stage, ''), ',' ORDER BY id)",
    "raw_objects": "count(*), string_agg(sha256, ',' ORDER BY id)",
    "data_quality_results": "count(*)",
    "reconciliation_results": "count(*)",
    "source_connections": "count(*)",
    "tenant_settings": "count(*), string_agg(key || value::text, ',' ORDER BY key)",
    "user_tenants": "count(*), string_agg(role, ',' ORDER BY user_id)",
    "pipeline_jobs": "count(*)",
}


def _assinatura(iso, tenant: str) -> dict:
    with iso.owner() as s:
        return {
            t: tuple(
                s.execute(text(f"SELECT {expr} FROM {t} WHERE tenant_id = :t"), {"t": tenant}).one()
            )
            for t, expr in _ASSINATURA.items()
        }


def _pacote(tmp: Path, seed: int) -> dict[str, bytes]:
    p = Path(data_platform_dir()) / "examples" / "generic_operator" / "generate_package.py"
    spec = importlib.util.spec_from_file_location("w2h_pkg_bk", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.gerar(tmp, 50, seed, date(2026, 1, 1), 3, True)
    return {f.name: f.read_bytes() for f in sorted(tmp.glob("*.csv"))}


@pytest.fixture(scope="module")
def bk(iso_env, tmp_path_factory):
    create_tenant(iso_env, BK)
    create_user(iso_env, "bk.admin@iso.example", tenant=BK, role="TENANT_ADMIN")
    sa = iso_client(iso_env, SUPERADMIN_EMAIL, None)
    fonte = sa.post(
        f"/api/admin/tenants/{BK}/sources",
        json={
            "name": "Pacote CSV",
            "source_type": "FILE",
            "source_system": "generic_csv",
            "configuration": {"mapping_id": "generic_operator", "mapping_version": 1},
        },
    ).json()["id"]
    r = upload_and_wait(sa, BK, fonte, _pacote(tmp_path_factory.mktemp("bk"), seed=55))
    assert r["status"] == "SUCCESS", r
    with iso_env.owner() as s:
        s.execute(
            text(
                "INSERT INTO tenant_settings (tenant_id, key, value) VALUES (:t, 'locale', '\"pt-BR\"') "
                "ON CONFLICT DO NOTHING"
            ),
            {"t": BK},
        )
        s.commit()
    return {"sa": sa, "fonte": fonte, "iso": iso_env, "tmp": tmp_path_factory}


def test_export_import_restaura_o_tenant_sem_tocar_os_outros(bk):
    iso, eng = bk["iso"], bk["iso"].owner.kw["bind"]
    antes = _assinatura(iso, BK)
    outro_antes = _assinatura(iso, TENANT_A)
    arq = bk["tmp"].mktemp("exp") / f"{BK}.tar.gz"
    m = export_tenant(eng, BK, arq)
    assert m["tenant_id"] == BK and m["raw_objects"]
    assert all(o["key"].startswith(f"tenant/{BK}/") for o in m["raw_objects"])
    # "incidente": dados apagados/alterados só deste tenant
    with iso.owner() as s:
        s.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": BK})
        s.execute(
            text("DELETE FROM eventos_assistenciais WHERE tenant_id = :t AND id % 2 = 0"), {"t": BK}
        )
        s.execute(
            text("UPDATE beneficiarios SET data_saida = '2026-02-01' WHERE tenant_id = :t"),
            {"t": BK},
        )
        s.execute(text("DELETE FROM tenant_settings WHERE tenant_id = :t"), {"t": BK})
        s.commit()
    assert _assinatura(iso, BK) != antes
    r = import_tenant(eng, arq, BK, confirm=BK)
    assert r["tabelas"]["eventos_assistenciais"] == antes["eventos_assistenciais"][0]
    assert _assinatura(iso, BK) == antes
    assert _assinatura(iso, TENANT_A) == outro_antes
    # a API continua funcionando para o tenant restaurado (sequências ajustadas, RLS ok)
    c = iso_client(iso, "bk.admin@iso.example", BK)
    assert c.get("/api/health").status_code == 200
    assert c.get("/api/auth/me").json()["tenant"]["id"] == BK


def test_import_recusa_tenant_errado_confirmacao_e_esquema(bk):
    eng = bk["iso"].owner.kw["bind"]
    arq = bk["tmp"].mktemp("exp2") / f"{BK}.tar.gz"
    export_tenant(eng, BK, arq, include_raw=False)
    with pytest.raises(TenantBackupError, match="confirmação"):
        import_tenant(eng, arq, BK, confirm="outro")
    with pytest.raises(TenantBackupError, match="outro tenant"):
        import_tenant(eng, arq, TENANT_A, confirm=TENANT_A)
    m, files = read_archive(arq)
    m["alembic_revision"] = "revisao-antiga"
    falso = arq.with_name("esquema.tar.gz")
    _reempacota(falso, m, files)
    with pytest.raises(TenantBackupError, match="esquema diferente"):
        import_tenant(eng, falso, BK, confirm=BK)


def test_arquivo_adulterado_e_recusado(bk):
    eng = bk["iso"].owner.kw["bind"]
    arq = bk["tmp"].mktemp("exp3") / f"{BK}.tar.gz"
    export_tenant(eng, BK, arq, include_raw=False)
    m, files = read_archive(arq)
    files["tables/receitas.csv"] = files["tables/receitas.csv"].replace(b",", b";", 1)
    adulterado = arq.with_name("adulterado.tar.gz")
    _reempacota(adulterado, m, files)
    with pytest.raises(TenantBackupError, match="adulterada"):
        import_tenant(eng, adulterado, BK, confirm=BK)
    # linha de outro tenant injetada (com sha256 recalculado) também é recusada
    import hashlib

    ev = files["tables/receitas.csv"].replace(b";", b",", 1)
    linhas = ev.decode().splitlines()
    if len(linhas) > 1:
        linhas[1] = linhas[1].replace(BK, TENANT_A)
        files["tables/receitas.csv"] = ("\n".join(linhas) + "\n").encode()
        for t in m["tables"]:
            if t["name"] == "receitas":
                t["sha256"] = hashlib.sha256(files["tables/receitas.csv"]).hexdigest()
        injetado = arq.with_name("injetado.tar.gz")
        _reempacota(injetado, m, files)
        with pytest.raises(TenantBackupError, match="outro tenant"):
            import_tenant(eng, injetado, BK, confirm=BK)


def test_raw_do_tenant_exportado_so_do_proprio_prefixo(bk):
    st = get_raw_storage()
    assert st.list(tenant_prefix(BK))
    eng = bk["iso"].owner.kw["bind"]
    m = export_tenant(eng, BK, bk["tmp"].mktemp("exp4") / "x.tar.gz")
    assert {o["key"] for o in m["raw_objects"]} == set(st.list(tenant_prefix(BK)))


def _reempacota(path: Path, manifest: dict, files: dict[str, bytes]) -> None:
    with tarfile.open(path, "w:gz") as tar:
        for nome, b in [("manifest.json", json.dumps(manifest).encode()), *files.items()]:
            info = tarfile.TarInfo(nome)
            info.size = len(b)
            tar.addfile(info, io.BytesIO(b))
