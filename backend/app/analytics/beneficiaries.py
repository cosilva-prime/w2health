"""Beneficiário / jornada simplificada — visão anonimizada e timeline assistencial."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.analytics import formulas as f
from app.core.faixas import idade_em
from app.repositories import analytics_repo as repo

# Ordem canônica da jornada assistencial (para a timeline).
ORDEM_JORNADA = {
    "consulta": 0, "exame": 1, "pronto_socorro": 1, "terapia": 3,
    "cirurgia": 4, "opme": 4, "internacao": 5,
}
ETAPA_JORNADA = {
    "consulta": "Consulta", "exame": "Exame", "pronto_socorro": "Pronto-socorro",
    "terapia": "Terapia", "cirurgia": "Procedimento", "opme": "Procedimento",
    "internacao": "Internação",
}


def _f(x) -> float:
    return float(x) if x is not None else 0.0


def lista(
    session: Session, competencia: date, page: int = 1, page_size: int = 25,
    faixa_etaria: str | None = None, sexo: str | None = None, id_plano: int | None = None,
) -> dict:
    rows, total = repo.beneficiarios_top(
        session, competencia, page_size, (page - 1) * page_size,
        faixa_etaria=faixa_etaria, sexo=sexo, id_plano=id_plano,
    )
    return {
        "competencia": competencia.isoformat(),
        "total": total, "page": page, "page_size": page_size,
        "itens": [
            {
                "id": r["id"], "codigo": r["codigo"], "sexo": r["sexo"],
                "faixa_etaria": r["faixa_etaria"], "regiao": r["regiao"], "plano": r["plano"],
                "despesa": round(_f(r["despesa"]), 2), "eventos": r["eventos"],
            }
            for r in rows
        ],
    }


def detalhe(session: Session, id_beneficiario: int) -> dict:
    info = repo.beneficiario_info(session, id_beneficiario)
    if info is None:
        raise ValueError("beneficiário não encontrado")
    serie = repo.beneficiario_serie(session, id_beneficiario)
    eventos = repo.beneficiario_eventos(session, id_beneficiario)

    despesa_total = sum(_f(e["valor_pago"]) for e in eventos)
    hoje = date.today()

    return {
        "beneficiario": {
            "id": info["id"],
            "codigo": info["codigo"],
            "sexo": info["sexo"],
            "idade": idade_em(info["data_nascimento"], hoje),
            "faixa_etaria": info["faixa_etaria"],
            "regiao": info["regiao"],
            "macrorregiao": info["macrorregiao"],
            "plano": info["plano"],
            "contrato": info["contrato"],
            "status": info["status"],
        },
        "resumo": {
            "despesa_total": round(despesa_total, 2),
            "eventos": len(eventos),
            "meses_com_evento": len(serie),
            "custo_medio_evento": round(despesa_total / len(eventos), 2) if eventos else 0.0,
        },
        "evolucao_mensal": [
            {
                "competencia": r["competencia"].isoformat(),
                "despesa": round(_f(r["despesa"]), 2),
                "eventos": r["eventos"],
            }
            for r in serie
        ],
        "eventos": [
            {
                "id": e["id"],
                "data": e["data_evento"].isoformat(),
                "competencia": e["competencia"].isoformat(),
                "tipo_atendimento": e["tipo_atendimento"],
                "procedimento": e["procedimento"],
                "grupo": e["grupo_procedimento"],
                "especialidade": e["especialidade"],
                "prestador": e["prestador"],
                "diagnostico": e["diagnostico"],
                "quantidade": e["quantidade"],
                "valor_apresentado": round(_f(e["valor_apresentado"]), 2),
                "valor_glosado": round(_f(e["valor_glosado"]), 2),
                "valor_pago": round(_f(e["valor_pago"]), 2),
            }
            for e in eventos
        ],
    }


def timeline(session: Session, id_beneficiario: int) -> dict:
    """Timeline simplificada: eventos ordenados por data, rotulados por etapa da jornada."""
    info = repo.beneficiario_info(session, id_beneficiario)
    if info is None:
        raise ValueError("beneficiário não encontrado")
    eventos = repo.beneficiario_eventos(session, id_beneficiario)
    itens = [
        {
            "data": e["data_evento"].isoformat(),
            "etapa": ETAPA_JORNADA.get(e["tipo_atendimento"], "Atendimento"),
            "ordem_jornada": ORDEM_JORNADA.get(e["tipo_atendimento"], 2),
            "tipo_atendimento": e["tipo_atendimento"],
            "procedimento": e["procedimento"],
            "especialidade": e["especialidade"],
            "prestador": e["prestador"],
            "diagnostico": e["diagnostico"],
            "valor_pago": round(_f(e["valor_pago"]), 2),
        }
        for e in eventos
    ]
    return {
        "beneficiario": {"id": info["id"], "codigo": info["codigo"]},
        "timeline": itens,
    }


def concentracao(session: Session, competencia: date, base: str = "beneficiario") -> dict:
    valores = repo.despesa_por_beneficiario(session, competencia)
    c = f.concentracao(valores, ks=(1, 3, 5, 10, 20, 100))
    n = c.n
    frase = None
    if n:
        for pct in (1, 5, 10):
            k = max(1, round(n * pct / 100))
            share = sum(sorted(valores, reverse=True)[:k]) / c.total if c.total else 0.0
            if pct == 5:
                frase = (
                    f"{pct}% dos beneficiários concentraram "
                    f"{round(share * 100, 1)}% da despesa assistencial do período."
                )
    return {
        "competencia": competencia.isoformat(),
        "base": base,
        "concentracao": c.as_dict(),
        "frase": frase,
        "metodologia": "top-k share, ponto de Pareto (share acumulado ≥ 80%) e índice de Gini.",
    }
