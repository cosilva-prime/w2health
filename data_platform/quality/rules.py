"""Regras mínimas de Data Quality do W2Health (v1.2).

**Independentes de fornecedor.** Operam sobre linhas do MODELO CANÔNICO (dicts), não
sobre o esquema de nenhuma origem. Cada regra tem uma severidade:

  * ERROR   — bloqueia o processamento da entidade (a carga não avança para Silver/Gold);
  * WARNING — permite continuar, mas registra o problema (`data_quality_results`);
  * INFO    — apenas informativo.

Uso (conceitual, num pipeline futuro):

    ctx = QualityContext(beneficiarios_ids={...}, contratos_ids={...}, prestadores_ids={...})
    violacoes = avaliar("evento_assistencial", linhas_canonicas, ctx)
    if any(v.severity == "ERROR" for v in violacoes):
        abortar_entidade()

Este módulo NÃO é executado por nenhum pipeline na v1.2 — existe como contrato e é
coberto por `backend/tests/test_data_quality.py`.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

ERROR, WARNING, INFO = "ERROR", "WARNING", "INFO"


@dataclass
class QualityContext:
    beneficiarios_ids: set = field(default_factory=set)
    contratos_ids: set = field(default_factory=set)
    prestadores_ids: set = field(default_factory=set)
    planos_ids: set = field(default_factory=set)


@dataclass
class Violation:
    rule_id: str
    severity: str
    entity: str
    message: str
    sample: dict


def _is_first_of_month(v) -> bool:
    if isinstance(v, date):
        return v.day == 1
    try:
        y, m, d = str(v).split("T")[0].split("-")
        return int(d) == 1 and 1 <= int(m) <= 12
    except Exception:
        return False


def _num(row: dict, key: str, default=0.0) -> float:
    try:
        return float(row.get(key, default) or 0.0)
    except (TypeError, ValueError):
        return float("nan")


# --------------------------------------------------------------------------- por entidade
def _check_evento(rows: Iterable[dict], ctx: QualityContext) -> list[Violation]:
    out: list[Violation] = []
    vistos: set = set()
    for r in rows:
        if not r.get("tenant_id"):
            out.append(Violation("tenant_id_ausente", ERROR, "evento_assistencial",
                                 "linha sem tenant_id", r))
        if ctx.beneficiarios_ids and r.get("id_beneficiario") not in ctx.beneficiarios_ids:
            out.append(Violation("benef_inexistente_em_evento", ERROR, "evento_assistencial",
                                 f"id_beneficiario {r.get('id_beneficiario')} não existe", r))
        if ctx.contratos_ids and r.get("id_contrato") is not None \
                and r.get("id_contrato") not in ctx.contratos_ids:
            out.append(Violation("contrato_inexistente", ERROR, "evento_assistencial",
                                 f"id_contrato {r.get('id_contrato')} não existe", r))
        if ctx.prestadores_ids and r.get("id_prestador") not in ctx.prestadores_ids:
            out.append(Violation("prestador_inexistente", ERROR, "evento_assistencial",
                                 f"id_prestador {r.get('id_prestador')} não existe", r))
        if not r.get("data_evento"):
            out.append(Violation("evento_sem_data", ERROR, "evento_assistencial",
                                 "data_evento ausente", r))
        if r.get("competencia") is not None and not _is_first_of_month(r["competencia"]):
            out.append(Violation("competencia_invalida", ERROR, "evento_assistencial",
                                 f"competência {r['competencia']} não é o 1º dia do mês", r))
        apres, glosa = _num(r, "valor_apresentado"), _num(r, "valor_glosado")
        pago, copart = _num(r, "valor_pago"), _num(r, "valor_coparticipacao")
        if apres < 0 or pago < 0:
            out.append(Violation("valor_negativo", ERROR, "evento_assistencial",
                                 "valor apresentado/pago negativo", r))
        if glosa > apres + 0.01:
            out.append(Violation("glosa_maior_que_apresentado", ERROR, "evento_assistencial",
                                 f"glosa {glosa} > apresentado {apres}", r))
        if "despesa_liquida" in r:
            liq = _num(r, "despesa_liquida")
            if abs(liq - (apres - glosa - copart)) > 0.01:
                out.append(Violation("despesa_liquida_inconsistente", WARNING, "evento_assistencial",
                                     "despesa_liquida != bruta - glosa - coparticipação", r))
        if copart > pago + 0.01:
            out.append(Violation("coparticipacao_acima_permitido", WARNING, "evento_assistencial",
                                 f"coparticipação {copart} > valor_pago {pago}", r))
        bk = (r.get("source_system"), r.get("source_record_id"))
        if bk != (None, None):
            if bk in vistos:
                out.append(Violation("evento_duplicado", WARNING, "evento_assistencial",
                                     f"chave de origem repetida {bk}", r))
            vistos.add(bk)
    return out


def _check_beneficiario(rows: Iterable[dict], ctx: QualityContext) -> list[Violation]:
    out: list[Violation] = []
    for r in rows:
        if not r.get("tenant_id"):
            out.append(Violation("tenant_id_ausente", ERROR, "beneficiario", "sem tenant_id", r))
        ad, sa = r.get("data_adesao"), r.get("data_saida")
        if ad and sa and str(sa) < str(ad):
            out.append(Violation("data_saida_antes_adesao", ERROR, "beneficiario",
                                 f"data_saida {sa} < data_adesao {ad}", r))
        if ctx.contratos_ids and r.get("id_contrato") not in ctx.contratos_ids:
            out.append(Violation("contrato_inexistente", ERROR, "beneficiario",
                                 f"id_contrato {r.get('id_contrato')} não existe", r))
    return out


def _check_receita(rows: Iterable[dict], ctx: QualityContext) -> list[Violation]:
    out: list[Violation] = []
    vistos: set = set()
    for r in rows:
        if not r.get("tenant_id"):
            out.append(Violation("tenant_id_ausente", ERROR, "receita", "sem tenant_id", r))
        if not _is_first_of_month(r.get("competencia")):
            out.append(Violation("competencia_invalida", ERROR, "receita",
                                 f"competência {r.get('competencia')} inválida", r))
        if _num(r, "receita_contraprestacao") < 0:
            out.append(Violation("valor_negativo", ERROR, "receita", "receita negativa", r))
        bk = (r.get("competencia"), r.get("id_plano"))
        if bk in vistos:
            out.append(Violation("receita_duplicada", WARNING, "receita",
                                 f"(competência, plano) repetido {bk}", r))
        vistos.add(bk)
    return out


_DISPATCH = {
    "evento_assistencial": _check_evento,
    "beneficiario": _check_beneficiario,
    "receita": _check_receita,
}


def avaliar(entity: str, rows: Iterable[dict], ctx: QualityContext | None = None) -> list[Violation]:
    ctx = ctx or QualityContext()
    fn = _DISPATCH.get(entity)
    if fn is None:
        return []
    return fn(list(rows), ctx)


def bloqueia_processamento(violacoes: Iterable[Violation]) -> bool:
    return any(v.severity == ERROR for v in violacoes)
