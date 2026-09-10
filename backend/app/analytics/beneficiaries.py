"""Beneficiário / jornada simplificada — visão anonimizada e timeline assistencial."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.analytics import formulas as f
from app.analytics.periodo import competencia_comparacao
from app.core.faixas import idade_em
from app.core.thresholds import ALTO_CUSTO_MES
from app.repositories import analytics_repo as repo

# Descritores de comportamento do beneficiário (v1.2, C5). São classificações puramente
# DESCRITIVAS a partir de despesa/eventos observados — nunca um score clínico nem uma
# previsão. Ver docs/DISCOVERY_GESTAO_SAUDE.md.
JANELA_RECORRENCIA = 6           # meses (incluindo o mês de referência)
LIMIAR_EVENTO_PONTUAL = 3_000.0  # R$ de despesa líquida para um evento pontual "de alto custo"

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
    id_contrato: int | None = None,
) -> dict:
    rows, total = repo.beneficiarios_top(
        session, competencia, page_size, (page - 1) * page_size,
        faixa_etaria=faixa_etaria, sexo=sexo, id_plano=id_plano, id_contrato=id_contrato,
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


def detalhe(session: Session, id_beneficiario: int, competencia: date | None = None) -> dict:
    info = repo.beneficiario_info(session, id_beneficiario)
    if info is None:
        raise ValueError("beneficiário não encontrado")
    serie = repo.beneficiario_serie(session, id_beneficiario)
    eventos = repo.beneficiario_eventos(session, id_beneficiario)

    despesa_total = sum(_f(e["valor_pago"]) for e in eventos)
    hoje = date.today()

    # v1.2 — bloco de comportamento (C5). Referência = `competencia` ou o último mês da série.
    ref = competencia
    if ref is None and serie:
        ref = max(r["competencia"] for r in serie)
    comportamento = None
    if ref is not None:
        comportamento = {
            "competencia_referencia": ref.isoformat(),
            "recorrencia": recorrencia(serie, ref),
            "participacao_variacao": participacao_variacao(session, id_beneficiario, ref),
            "eventos_pontuais_alto_custo": eventos_pontuais_alto_custo(session, id_beneficiario),
        }

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
                "despesa_liquida": round(_f(r["despesa_liquida"]), 2),
                "eventos": r["eventos"],
            }
            for r in serie
        ],
        "comportamento": comportamento,
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


# =====================================================================================
# v1.2 — C5: descritores de comportamento do beneficiário (nunca score clínico/preditivo)
# =====================================================================================
def _classificar_recorrencia(meses_com_evento: int) -> str:
    if meses_com_evento >= 4:
        return "utilizador_frequente"
    if meses_com_evento >= 2:
        return "recorrente"
    return "esporadico"


def recorrencia(serie: list[dict], competencia: date, janela: int = JANELA_RECORRENCIA) -> dict:
    """Nº de meses com evento na janela terminando em `competencia` (inclusive) +
    classificação descritiva. `serie` = saída de `repo.beneficiario_serie`."""
    comp_iso = competencia.isoformat()
    ordenada = sorted(serie, key=lambda r: r["competencia"].isoformat())
    ate_idx = [i for i, r in enumerate(ordenada) if r["competencia"].isoformat() <= comp_iso]
    fim = (ate_idx[-1] + 1) if ate_idx else len(ordenada)
    janela_rows = ordenada[max(0, fim - janela): fim]
    meses = sum(1 for r in janela_rows if (r["eventos"] or 0) > 0)
    return {
        "janela_meses": janela,
        "meses_com_evento": meses,
        "classificacao": _classificar_recorrencia(meses),
        "metodologia": (
            f"contagem de meses com ≥1 evento nos últimos {janela} meses; "
            "classificação descritiva (esporádico / recorrente / utilizador frequente)."
        ),
    }


def eventos_pontuais_alto_custo(session: Session, id_beneficiario: int) -> list[dict]:
    """Eventos de procedimento com `perfil_utilizacao='pontual'`, despesa líquida acima
    de `LIMIAR_EVENTO_PONTUAL` e que NÃO se repetem (procedimento aparece 1x na série do
    beneficiário)."""
    eventos = repo.eventos_pontuais_do_beneficiario(session, id_beneficiario)
    contagem: dict[str, int] = {}
    for e in eventos:
        contagem[e["procedimento"]] = contagem.get(e["procedimento"], 0) + 1
    out = []
    for e in eventos:
        liq = _f(e["despesa_liquida"])
        if liq >= LIMIAR_EVENTO_PONTUAL and contagem[e["procedimento"]] == 1:
            out.append({
                "competencia": e["competencia"].isoformat(),
                "data": e["data_evento"].isoformat(),
                "procedimento": e["procedimento"],
                "grupo": e["grupo_procedimento"],
                "despesa_liquida": round(liq, 2),
                "nao_recorrente": True,
            })
    return out


def participacao_variacao(
    session: Session, id_beneficiario: int, competencia: date, comparacao: str = "mes_anterior"
) -> dict:
    """Δdespesa líquida do beneficiário / Δdespesa líquida total da carteira (%),
    com a mesma proteção contra cancelamento usada em `formulas.contribuicoes`."""
    comp_ant = competencia_comparacao(competencia, comparacao)
    deltas = repo.beneficiarios_delta_mes(session, competencia, comp_ant)
    total = sum(v["delta"] for v in deltas.values())
    soma_abs = sum(abs(v["delta"]) for v in deltas.values()) or 1.0
    denom = total if abs(total) >= 0.15 * soma_abs else soma_abs
    d = deltas.get(id_beneficiario, {}).get("delta", 0.0)
    pct = (d / denom * 100.0) if abs(denom) > 1e-9 else 0.0
    return {
        "competencia": competencia.isoformat(),
        "comparacao": comparacao,
        "delta_beneficiario": round(d, 2),
        "delta_total_carteira": round(total, 2),
        "participacao_pct": round(abs(pct), 3),
    }


def novos_casos_alto_custo(
    session: Session, competencia: date, comparacao: str = "mes_anterior",
    limiar: float = ALTO_CUSTO_MES, contrato_id: int | None = None,
) -> dict:
    """Beneficiários que cruzaram o limiar de despesa líquida no mês SEM histórico
    relevante nos meses anteriores (C5). Descritivo — não é previsão."""
    itens = repo.beneficiarios_novo_caso_alto_custo(
        session, competencia, meses_baseline=JANELA_RECORRENCIA, limiar=limiar,
        id_contrato=contrato_id,
    )
    return {
        "competencia": competencia.isoformat(),
        "limiar": limiar,
        "total": len(itens),
        "itens": [
            {
                "id": r["id"], "codigo": r["codigo"], "id_contrato": r["id_contrato"],
                "despesa_liquida": round(_f(r["despesa_liquida"]), 2),
                "maior_despesa_anterior": round(_f(r["max_ant"]), 2),
            }
            for r in itens
        ],
        "metodologia": (
            f"despesa líquida do mês ≥ {limiar:.0f} e maior despesa líquida mensal nos "
            f"{JANELA_RECORRENCIA} meses anteriores < {limiar * 0.25:.0f}."
        ),
    }
