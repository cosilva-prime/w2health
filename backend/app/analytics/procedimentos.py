"""Procedimentos — lista, detalhe e bridge frequência × custo médio."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.analytics import formulas as f
from app.analytics.periodo import competencia_comparacao
from app.repositories import analytics_repo as repo


def _f(x) -> float:
    return float(x) if x is not None else 0.0


def lista(session: Session, competencia: date, sort: str = "despesa",
          page: int = 1, page_size: int = 25) -> dict:
    dim = repo.dimensao_mes(session, competencia, "procedimento")
    rows = [{"id": int(k), **v} for k, v in dim.items()]
    keymap = {
        "despesa": lambda r: _f(r["despesa"]),
        "eventos": lambda r: r["eventos"],
        "custo_medio": lambda r: _f(r["custo_medio"]),
        "beneficiarios": lambda r: r["beneficiarios"],
    }
    rows.sort(key=keymap.get(sort, keymap["despesa"]), reverse=True)
    total = len(rows)
    ini = (page - 1) * page_size
    return {
        "competencia": competencia.isoformat(),
        "total": total, "page": page, "page_size": page_size,
        "itens": [
            {
                "id": r["id"], "descricao": r["rotulo"],
                "despesa": round(_f(r["despesa"]), 2), "eventos": r["eventos"],
                "quantidade": r["quantidade"], "beneficiarios": r["beneficiarios"],
                "custo_medio": round(_f(r["custo_medio"]), 2),
                "freq_por_mil": round(_f(r["freq_por_mil"]), 3),
            }
            for r in rows[ini: ini + page_size]
        ],
    }


def bridge(session: Session, id_procedimento: int, competencia: date,
           comparacao: str = "mes_anterior", metodo: str = "bennet") -> dict:
    comp_ant = competencia_comparacao(competencia, comparacao)
    a = repo.dimensao_mes(session, comp_ant, "procedimento").get(str(id_procedimento))
    b = repo.dimensao_mes(session, competencia, "procedimento").get(str(id_procedimento))
    n0 = _f(a["eventos"]) if a else 0.0
    n1 = _f(b["eventos"]) if b else 0.0
    p0 = (_f(a["despesa"]) / n0) if n0 else 0.0
    p1 = (_f(b["despesa"]) / n1) if n1 else 0.0
    br = f.bridge(n0, p0, n1, p1, metodo=metodo)
    return {
        "id_procedimento": id_procedimento,
        "competencia": competencia.isoformat(),
        "comparacao": comparacao,
        "descricao": (b or a or {}).get("rotulo"),
        "bridge": br.as_dict(),
        "metodologia": "ΔD = n1·p1 − n0·p0; efeitos por Bennet (simétrico, sem resíduo).",
    }


def detalhe(session: Session, id_procedimento: int, competencia: date,
            comparacao: str = "mes_anterior") -> dict:
    serie = repo.dimensao_serie(session, "procedimento", str(id_procedimento))
    if not serie:
        raise ValueError("procedimento sem eventos")
    return {
        "id_procedimento": id_procedimento,
        "descricao": serie[-1]["rotulo"],
        "competencia": competencia.isoformat(),
        "bridge": bridge(session, id_procedimento, competencia, comparacao)["bridge"],
        "serie": [
            {
                "competencia": r["competencia"].isoformat(),
                "despesa": round(_f(r["despesa"]), 2),
                "eventos": r["eventos"],
                "custo_medio": round(_f(r["custo_medio"]), 2),
                "freq_por_mil": round(_f(r["freq_por_mil"]), 3),
            }
            for r in serie
        ],
        "top_prestadores": repo.eventos_da_categoria(
            session, competencia, "procedimento", str(id_procedimento),
            agrupar_por="prestador", limit=10,
        ),
    }
