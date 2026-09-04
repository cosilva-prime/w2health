"""Análise de coortes — o "porquê do porquê" (v1.1, Etapa A).

Uma camada abaixo de `decomposition.explicar()` / `drill()`: para um fator já
identificado (dimensão, chave), classifica os beneficiários que compõem a variação da
despesa em coortes (novos, recorrentes, deixaram de utilizar) com **identidade
matemática exata** — a soma das coortes reconcilia com a variação observada, o mesmo
princípio já usado no bridge de Bennet.

Regra inegociável: o motor NUNCA afirma causalidade sem evidência. Todo achado carrega
`tipo_evidencia` (FATO | HIPOTESE | A_INVESTIGAR) e `nivel_confianca` (ALTA | MEDIA |
BAIXA). Ver `docs/ANALYTICS_ENGINE.md` para a tabela de regras.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from app.analytics import formulas as f
from app.analytics.periodo import competencia_comparacao
from app.repositories import analytics_repo as repo

EPS = 1e-9

FATO = "FATO"
HIPOTESE = "HIPOTESE"
A_INVESTIGAR = "A_INVESTIGAR"

ALTA, MEDIA, BAIXA = "ALTA", "MEDIA", "BAIXA"

LIMIAR_PERFIL_PONTUAL = 0.60  # fração de despesa em procs "pontuais" p/ elegibilidade da hipótese

_ROTULO_EFEITO = {"frequencia": "frequência", "custo_medio": "custo médio", "misto": "misto"}


@dataclass
class Evidencia:
    tipo_evidencia: str
    nivel_confianca: str
    texto: str
    metricas: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "tipo_evidencia": self.tipo_evidencia,
            "nivel_confianca": self.nivel_confianca,
            "texto": self.texto,
            "metricas": self.metricas,
        }


@dataclass
class CoorteBucket:
    codigo: str
    rotulo: str
    n_beneficiarios: int
    despesa_anterior: float
    despesa_atual: float
    delta: float
    participacao_variacao: float
    evidencias: list[Evidencia]
    beneficiarios_amostra: list[dict]

    def as_dict(self) -> dict:
        return {
            "codigo": self.codigo,
            "rotulo": self.rotulo,
            "n_beneficiarios": self.n_beneficiarios,
            "despesa_anterior": round(self.despesa_anterior, 2),
            "despesa_atual": round(self.despesa_atual, 2),
            "delta": round(self.delta, 2),
            "participacao_variacao": round(self.participacao_variacao, 2),
            "evidencias": [e.as_dict() for e in self.evidencias],
            "beneficiarios_amostra": self.beneficiarios_amostra,
        }


def _amostra(ids: list[int], status: dict[int, dict], valores: dict[int, float], n: int = 6) -> list[dict]:
    ordenados = sorted(ids, key=lambda i: abs(valores.get(i, 0.0)), reverse=True)[:n]
    return [
        {
            "id": i,
            "codigo": status.get(i, {}).get("codigo", f"#{i}"),
            "valor": round(valores.get(i, 0.0), 2),
        }
        for i in ordenados
    ]


def _participacao(delta: float, denom_total: float, soma_abs: float) -> float:
    if soma_abs < EPS:
        return 0.0
    denom = denom_total if abs(denom_total) >= 0.15 * soma_abs else soma_abs
    return (delta / denom * 100.0) if abs(denom) > EPS else 0.0


def analisar_causas(
    session: Session, dimensao: str, chave: str, competencia: date, comparacao: str = "mes_anterior"
) -> dict:
    comp_ant = competencia_comparacao(competencia, comparacao)

    pop0 = repo.beneficiarios_da_categoria(session, comp_ant, dimensao, chave)
    pop1 = repo.beneficiarios_da_categoria(session, competencia, dimensao, chave)
    b0, b1 = set(pop0), set(pop1)

    novos_ids = sorted(b1 - b0)
    recorrentes_ids = sorted(b0 & b1)
    saida_utilizacao_ids = sorted(b0 - b1)

    todos_ids = sorted(b0 | b1)
    status = repo.beneficiarios_status_bulk(session, todos_ids)

    despesa_ant_total = sum(v["despesa"] for v in pop0.values())
    despesa_atu_total = sum(v["despesa"] for v in pop1.values())
    delta_total = despesa_atu_total - despesa_ant_total

    buckets: list[CoorteBucket] = []
    deltas_brutos: dict[str, float] = {}

    # ------------------------------------------------------------- NOVOS USUÁRIOS
    if novos_ids:
        d_novos = {i: pop1[i]["despesa"] for i in novos_ids}
        novos_carteira = [i for i in novos_ids if status.get(i, {}).get("data_adesao") and status[i]["data_adesao"] > comp_ant]
        novos_categoria = [i for i in novos_ids if i not in novos_carteira]

        for cod, rot, ids_sub in (
            ("novos_carteira", "Novos na carteira (aderiram no período)", novos_carteira),
            ("novos_categoria", "Já ativos, novos nesta categoria no período", novos_categoria),
        ):
            if not ids_sub:
                continue
            d_sub = sum(d_novos[i] for i in ids_sub)
            deltas_brutos[cod] = d_sub
            buckets.append(
                CoorteBucket(
                    codigo=cod, rotulo=rot, n_beneficiarios=len(ids_sub),
                    despesa_anterior=0.0, despesa_atual=d_sub, delta=d_sub,
                    participacao_variacao=0.0,
                    evidencias=[Evidencia(
                        FATO, ALTA,
                        f"{len(ids_sub)} beneficiário(s) sem despesa nesta categoria no período "
                        f"anterior passaram a ter, somando R$ {d_sub:,.0f}.".replace(",", "."),
                        {"n_beneficiarios": len(ids_sub), "despesa": round(d_sub, 2)},
                    )],
                    beneficiarios_amostra=_amostra(ids_sub, status, d_novos),
                )
            )

    # ------------------------------------------------------------- RECORRENTES
    if recorrentes_ids:
        d0_rec = sum(pop0[i]["despesa"] for i in recorrentes_ids)
        d1_rec = sum(pop1[i]["despesa"] for i in recorrentes_ids)
        n0_rec = sum(pop0[i]["eventos"] for i in recorrentes_ids)
        n1_rec = sum(pop1[i]["eventos"] for i in recorrentes_ids)
        delta_rec = d1_rec - d0_rec
        deltas_brutos["recorrentes"] = delta_rec

        p0 = d0_rec / n0_rec if n0_rec else 0.0
        p1 = d1_rec / n1_rec if n1_rec else 0.0
        bridge = f.bennet_bridge(n0_rec, p0, n1_rec, p1).as_dict()

        prest_ant = repo.prestadores_por_beneficiario_na_categoria(session, comp_ant, dimensao, chave, recorrentes_ids)
        prest_atu = repo.prestadores_por_beneficiario_na_categoria(session, competencia, dimensao, chave, recorrentes_ids)
        trocaram = [i for i in recorrentes_ids if prest_ant.get(i) and prest_atu.get(i) and not (prest_ant[i] & prest_atu[i])]

        evidencias = [
            Evidencia(
                FATO, ALTA,
                f"{len(recorrentes_ids)} beneficiário(s) usaram a categoria em ambos os "
                f"períodos; variação líquida de R$ {delta_rec:,.0f}.".replace(",", "."),
                {"n_beneficiarios": len(recorrentes_ids)},
            ),
            Evidencia(
                FATO, ALTA,
                f"Entre os recorrentes, o efeito principal foi "
                f"{_ROTULO_EFEITO.get(bridge['efeito_principal'], 'misto')} "
                f"(frequência {bridge['variacao_frequencia_pct']}%, "
                f"custo médio {bridge['variacao_custo_medio_pct']}%).",
                {"efeito_principal": bridge["efeito_principal"],
                 "variacao_frequencia_pct": bridge["variacao_frequencia_pct"],
                 "variacao_custo_medio_pct": bridge["variacao_custo_medio_pct"]},
            ),
        ]
        if trocaram:
            evidencias.append(Evidencia(
                FATO, ALTA,
                f"{len(trocaram)} beneficiário(s) recorrentes trocaram de prestador nesta categoria "
                "entre os dois períodos.",
                {"n_beneficiarios": len(trocaram)},
            ))

        buckets.append(
            CoorteBucket(
                codigo="recorrentes", rotulo="Permaneceram utilizando (recorrentes)",
                n_beneficiarios=len(recorrentes_ids), despesa_anterior=d0_rec,
                despesa_atual=d1_rec, delta=delta_rec, participacao_variacao=0.0,
                evidencias=evidencias,
                beneficiarios_amostra=_amostra(
                    recorrentes_ids, status,
                    {i: pop1[i]["despesa"] - pop0[i]["despesa"] for i in recorrentes_ids},
                ),
            )
        )

    # ------------------------------------------------------------- DEIXARAM DE UTILIZAR
    if saida_utilizacao_ids:
        saida_carteira = [
            i for i in saida_utilizacao_ids
            if status.get(i, {}).get("status") == "inativo"
            or (status.get(i, {}).get("data_saida") and status[i]["data_saida"] <= competencia)
        ]
        permanece_sem_evento = [i for i in saida_utilizacao_ids if i not in saida_carteira]

        if saida_carteira:
            d_sub = sum(pop0[i]["despesa"] for i in saida_carteira)
            deltas_brutos["saida_carteira"] = -d_sub
            buckets.append(
                CoorteBucket(
                    codigo="saida_carteira", rotulo="Saíram da carteira",
                    n_beneficiarios=len(saida_carteira), despesa_anterior=d_sub,
                    despesa_atual=0.0, delta=-d_sub, participacao_variacao=0.0,
                    evidencias=[Evidencia(
                        FATO, ALTA,
                        f"{len(saida_carteira)} beneficiário(s) com despesa nesta categoria no "
                        f"período anterior (R$ {d_sub:,.0f}) saíram da carteira (status/data de "
                        "saída registrados).".replace(",", "."),
                        {"n_beneficiarios": len(saida_carteira), "despesa_anterior": round(d_sub, 2)},
                    )],
                    beneficiarios_amostra=_amostra(saida_carteira, status, {i: pop0[i]["despesa"] for i in saida_carteira}),
                )
            )

        if permanece_sem_evento:
            d_sub = sum(pop0[i]["despesa"] for i in permanece_sem_evento)
            deltas_brutos["permaneceram_sem_evento"] = -d_sub
            perfil = repo.perfil_utilizacao_despesa(session, comp_ant, dimensao, chave, permanece_sem_evento)
            total_perfil = sum(perfil.values()) or 1.0
            share_pontual = perfil.get("pontual", 0.0) / total_perfil

            fato = Evidencia(
                FATO, ALTA,
                f"{len(permanece_sem_evento)} beneficiário(s) permaneceram ativos na carteira, mas "
                f"não tiveram novo evento nesta categoria no período atual (despesa anterior de "
                f"R$ {d_sub:,.0f} que não se repetiu).".replace(",", "."),
                {"n_beneficiarios": len(permanece_sem_evento), "despesa_anterior": round(d_sub, 2)},
            )
            if share_pontual >= LIMIAR_PERFIL_PONTUAL:
                hipotese = Evidencia(
                    HIPOTESE, MEDIA,
                    f"{share_pontual*100:.0f}% dessa despesa anterior é de procedimentos de perfil "
                    "tipicamente pontual (cirurgia/internação/OPME) — padrão compatível com "
                    "conclusão de episódio assistencial pontual. Não há dado para confirmar "
                    "encerramento de tratamento.",
                    {"share_pontual": round(share_pontual, 3)},
                )
                evidencias_sub = [fato, hipotese]
            else:
                investigar = Evidencia(
                    A_INVESTIGAR, BAIXA,
                    "Os procedimentos anteriores desse grupo são majoritariamente recorrentes ou "
                    "variáveis — nenhum padrão conclusivo nos dados disponíveis; recomenda-se "
                    "investigação manual.",
                    {"share_pontual": round(share_pontual, 3)},
                )
                evidencias_sub = [fato, investigar]

            buckets.append(
                CoorteBucket(
                    codigo="permaneceram_sem_evento",
                    rotulo="Permaneceram na carteira sem novo evento",
                    n_beneficiarios=len(permanece_sem_evento), despesa_anterior=d_sub,
                    despesa_atual=0.0, delta=-d_sub, participacao_variacao=0.0,
                    evidencias=evidencias_sub,
                    beneficiarios_amostra=_amostra(permanece_sem_evento, status, {i: pop0[i]["despesa"] for i in permanece_sem_evento}),
                )
            )

    # ------------------------------------------------------------- participação + reconciliação
    soma_abs = sum(abs(v) for v in deltas_brutos.values())
    for bkt in buckets:
        bkt.participacao_variacao = _participacao(bkt.delta, delta_total, soma_abs)

    soma_buckets = sum(b.delta for b in buckets)
    reconciliacao_ok = abs(soma_buckets - delta_total) < 0.01

    return {
        "competencia": competencia.isoformat(),
        "comparacao": comparacao,
        "competencia_comparacao": comp_ant.isoformat(),
        "dimensao": dimensao,
        "chave": chave,
        "despesa_anterior": round(despesa_ant_total, 2),
        "despesa_atual": round(despesa_atu_total, 2),
        "delta_total": round(delta_total, 2),
        "coortes": [b.as_dict() for b in buckets],
        "reconciliacao": {
            "soma_coortes": round(soma_buckets, 2),
            "delta_observado": round(delta_total, 2),
            "ok": reconciliacao_ok,
        },
        "metodologia": (
            "Δdespesa = Σ(novos)·despesa_atual + Σ(recorrentes)·Δdespesa − Σ(deixaram de "
            "utilizar)·despesa_anterior — identidade exata (mesma lógica do bridge de Bennet). "
            "Toda evidência é classificada como FATO (dado observado), HIPÓTESE (padrão "
            "compatível, confiança média, exige perfil de utilização predominantemente pontual) "
            "ou A_INVESTIGAR (sem padrão suficiente) — nunca se afirma causalidade sem evidência."
        ),
    }
