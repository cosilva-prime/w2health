"""Baseline de performance LOCAL (não é SLA) — pipeline assíncrono e endpoints principais.

Uso (stack do docker compose no ar; credenciais só por variável de ambiente):

    PERF_ADMIN_EMAIL=... PERF_ADMIN_PASSWORD=...   # SUPER_ADMIN (cria tenant/fonte e carrega)
    PERF_USER_EMAIL=...  PERF_USER_PASSWORD=...    # usuário de um tenant com dados (endpoints)
    PERF_USER_TENANT=w2h-demo
    python scripts/perf_baseline.py --api http://localhost:8010/api --pacote <dir> --tenant perf-csv

Mede:
* pipeline: tempo da requisição de upload (recepção + RAW + enfileiramento), espera na fila,
  e a duração de cada passo registrada pelo worker (`pipeline_runs.steps`);
* endpoints: p50/p95/máximo de N chamadas sequenciais a cada rota analítica principal.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from pathlib import Path

import httpx


def login(c: httpx.Client, email: str, senha: str, tenant: str | None = None) -> None:
    r = c.post("/auth/login", json={"email": email, "password": senha, **({"tenant": tenant} if tenant else {})})
    r.raise_for_status()
    j = r.json()
    if j.get("status") != "ok":
        raise SystemExit(f"login exige etapa adicional ({j.get('status')}) — use um usuário sem MFA no ambiente local")
    c.headers["Authorization"] = "Bearer " + j["access_token"]


def pipeline(api: str, pacote: Path, tenant: str) -> dict:
    c = httpx.Client(base_url=api, timeout=600)
    login(c, os.environ["PERF_ADMIN_EMAIL"], os.environ["PERF_ADMIN_PASSWORD"])
    c.post("/admin/tenants", json={"code": tenant, "name": f"Perf {tenant}", "plan_code": "ENTERPRISE",
                                   "is_synthetic": True})
    fontes = c.get(f"/admin/tenants/{tenant}/sources").json()["itens"]
    fonte = next((f["id"] for f in fontes if f["source_type"] == "FILE"), None)
    if fonte is None:
        fonte = c.post(f"/admin/tenants/{tenant}/sources", json={
            "name": "Pacote perf", "source_type": "FILE", "source_system": "generic_csv",
            "configuration": {"mapping_id": "generic_operator", "mapping_version": 1}}).json()["id"]
    files = [("files", (p.name, p.read_bytes(), "text/csv")) for p in sorted(pacote.glob("*.csv"))]
    tamanho = sum(len(f[1][1]) for f in files)
    t0 = time.perf_counter()
    r = c.post(f"/admin/tenants/{tenant}/sources/{fonte}/uploads", files=files)
    req_ms = (time.perf_counter() - t0) * 1000
    out = r.json()
    if out.get("status") != "QUEUED":
        return {"erro": out.get("message"), "status": out.get("status")}
    run_id = out["ingestion_run_id"]
    while True:
        d = c.get(f"/admin/tenants/{tenant}/ingestion-runs/{run_id}").json()
        if d["run"]["status"] not in ("QUEUED", "RUNNING"):
            break
        time.sleep(1)
    total_ms = (time.perf_counter() - t0) * 1000
    job = d.get("job") or {}
    return {
        "pacote_bytes": tamanho, "registros": out["received"], "status": d["run"]["status"],
        "requisicao_upload_ms": round(req_ms), "fim_a_fim_ms": round(total_ms),
        "job_duracao_ms": job.get("duration_ms"), "tentativas": job.get("attempts"),
        "passos_ms": {s["stage"]: s["ms"] for s in d["steps"] if s["stage"] not in ("attempt",)},
        "reconciliacao": d["reconciliation_status"],
    }


ENDPOINTS = [
    "/executive/overview?competencia={c}&comparacao=mes_anterior",
    "/analytics/sinistralidade?competencia={c}&comparacao=mes_anterior",
    "/analytics/sinistralidade/explain?competencia={c}&comparacao=mes_anterior&dimensao=especialidade",
    "/analytics/sinistralidade/composicao?competencia={c}&comparacao=mes_anterior",
    "/analytics/contratos?competencia={c}&comparacao=mes_anterior",
    "/analytics/prestadores?competencia={c}&comparacao=mes_anterior&page_size=30&sort=despesa",
    "/analytics/prestadores/anomalias?competencia={c}&comparacao=mes_anterior",
    "/analytics/beneficiarios?competencia={c}&comparacao=mes_anterior",
    "/analytics/insights?competencia={c}&comparacao=mes_anterior",
]


def endpoints(api: str, competencia: str, n: int) -> dict:
    c = httpx.Client(base_url=api, timeout=120)
    login(c, os.environ["PERF_USER_EMAIL"], os.environ["PERF_USER_PASSWORD"], os.environ.get("PERF_USER_TENANT"))
    out = {}
    for e in ENDPOINTS:
        url = e.format(c=competencia)
        c.get(url)  # aquecimento
        tempos, status = [], set()
        for _ in range(n):
            t0 = time.perf_counter()
            r = c.get(url)
            tempos.append((time.perf_counter() - t0) * 1000)
            status.add(r.status_code)
        tempos.sort()
        out[url.split("?")[0]] = {"p50_ms": round(statistics.median(tempos)),
                                  "p95_ms": round(tempos[int(0.95 * (len(tempos) - 1))]),
                                  "max_ms": round(tempos[-1]), "status": sorted(status)}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8010/api")
    ap.add_argument("--pacote", type=Path)
    ap.add_argument("--tenant", default="perf-csv")
    ap.add_argument("--competencia", default="2026-06")
    ap.add_argument("-n", type=int, default=20)
    a = ap.parse_args()
    res = {}
    if a.pacote:
        res["pipeline"] = pipeline(a.api, a.pacote, a.tenant)
    if os.environ.get("PERF_USER_EMAIL"):
        res["endpoints"] = endpoints(a.api, a.competencia, a.n)
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
