"""Cenários intencionais plantados na base sintética (Etapa 4).

Cada cenário é um *hook* executado por competência dentro de `generate_eventos`; ele
injeta eventos rotulados (`cenario_tag`) calibrados por `k = n_beneficiarios / 20000`,
de forma reprodutível. O gabarito (`cenarios_gabarito`) guarda a verdade-fundamental
que os testes de integração comparam com a saída do motor analítico.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

import numpy as np

from app.models import CenarioGabarito
from app.seed.config import SeedConfig
from app.seed.generator import Carteira, Catalogo, new_event_row

Hook = Callable[[dict], list[dict] | None]


def _proc_index(cat: Catalogo) -> dict[str, dict]:
    """codigo do procedimento -> {id, espec_id, custo, tipo, slug}."""
    idx: dict[str, dict] = {}
    slug_by_espid = {v: k for k, v in cat.espec_id.items()}
    for slug, procs in cat.proc_by_espec.items():
        for p in procs:
            idx[p["codigo"]] = {
                "id": p["id"],
                "espec_id": cat.espec_id[slug],
                "custo": p["custo_base"],
                "tipo": p["tipo"],
                "slug": slug,
            }
    _ = slug_by_espid
    return idx


def _idade_inicio(cart: Carteira, cfg: SeedConfig) -> np.ndarray:
    ini_ym = cfg.inicio.year * 12 + cfg.inicio.month
    return ((ini_ym - cart.idade_ym) // 12).astype(int)


def _prov_pick(cat: Catalogo, slug: str, pos: int) -> tuple[int, int, float]:
    """Retorna (id_prestador, id_regiao, nivel_preco) do prestador `pos` da especialidade."""
    p = cat.prest_by_espec[slug]
    i = int(pos % len(p["ids"]))
    return int(p["ids"][i]), int(p["regiao"][i]), float(p["nivel"][i])


def _active_positions(ctx: dict, cohort: np.ndarray) -> np.ndarray:
    """Interseção do cohort (posições em cart.ids) com os ativos do mês."""
    active = set(ctx["a_idx"].tolist())
    return np.array([p for p in cohort if p in active], dtype=int)


def build_scenarios(
    cat: Catalogo, cfg: SeedConfig, rng: np.random.Generator, cart: Carteira
) -> tuple[
    list[Hook], list[CenarioGabarito], set[int], set[int], set[int],
    dict[date, float], dict[date, float], dict[date, float],
]:
    pidx = _proc_index(cat)
    idade0 = _idade_inicio(cart, cfg)
    k = cfg.n_beneficiarios / 20_000.0
    n = cfg.n_beneficiarios
    hooks: list[Hook] = []
    gaba: list[CenarioGabarito] = []
    rc = np.random.default_rng(cfg.seed + 777)  # rng dedicado aos cohorts (estável)

    def cohort(mask: np.ndarray, size: int) -> np.ndarray:
        cand = np.nonzero(mask)[0]
        if cand.size == 0:
            return cand
        return rc.choice(cand, size=min(size, cand.size), replace=False)

    def nround(x: float) -> int:
        return max(int(round(x)), 1)

    # ============================================================= S1 — CATARATA (frequência)
    cat_proc = pidx["CIR-CAT"]
    s1_cohort = cohort(idade0 >= 58, nround(1400 * k))
    s1_provs = [_prov_pick(cat, "oftalmologia", i) for i in range(3)]
    S1_TAG = "s1_catarata_freq"
    S1_ALVO = date(2026, 7, 1)

    def hook_catarata(ctx: dict) -> list[dict]:
        t: date = ctx["t"]
        r: np.random.Generator = ctx["rng"]
        pos = _active_positions(ctx, s1_cohort)
        if pos.size == 0:
            return []
        base = nround(58 * k)
        spike = t in (date(2026, 7, 1), date(2026, 8, 1))
        total = base + (nround(60 * k) if spike else 0)
        fator_custo = 1.03 if spike else 1.0
        chosen = r.choice(pos, size=min(total, pos.size), replace=False) if total <= pos.size \
            else r.choice(pos, size=total, replace=True)
        rows = []
        for j, bp in enumerate(chosen):
            # 68% do excedente em 3 prestadores; restante espalhado
            if spike and j >= base and (j - base) < 0.68 * (total - base):
                prov = s1_provs[(j - base) % 3]
            else:
                prov = _prov_pick(cat, "oftalmologia", int(r.integers(0, 999)))
            rows.append(
                new_event_row(
                    t=t, rng=r, id_beneficiario=int(cart.ids[bp]),
                    id_prestador=prov[0], id_procedimento=cat_proc["id"],
                    id_especialidade=cat_proc["espec_id"], id_regiao=int(cart.regiao_id[bp]),
                    tipo_atendimento="cirurgia", custo=cat_proc["custo"],
                    nivel_preco=prov[2], fator_custo=fator_custo, cenario_tag=S1_TAG,
                )
            )
        return rows

    hooks.append(hook_catarata)
    gaba.append(CenarioGabarito(
        codigo=S1_TAG, nome="Aumento de catarata por frequência",
        competencia_alvo=S1_ALVO, dimensao="procedimento", chave_alvo=str(cat_proc["id"]),
        rotulo_alvo="Facectomia com implante de LIO (catarata)", efeito_esperado="frequencia",
        descricao="Jul/2026: salto de ~35%+ na frequência de facectomia, custo médio ~+3%, "
                  "excedente concentrado em 3 prestadores de oftalmologia.",
        params={"tag": S1_TAG, "k": k, "spike_meses": ["2026-07", "2026-08"],
                "prestadores_alvo": [p[0] for p in s1_provs]},
    ))

    # ============================================================ S2 — INTERNAÇÕES (frequência, 60+)
    s2_procs = [pidx[c] for c in ("INT-PNM", "INT-ICC", "INT-AVC", "INT-DPOC", "INT-IAM", "INT-ITU")]
    s2_cohort_idoso = cohort(idade0 >= 60, nround(2500 * k))
    s2_cohort_geral = cohort(idade0 >= 30, nround(2500 * k))
    S2_TAG = "s2_internacoes"
    S2_ALVO = date(2026, 9, 1)

    def hook_internacoes(ctx: dict) -> list[dict]:
        t, r = ctx["t"], ctx["rng"]
        base = nround(22 * k)
        spike = t in (date(2026, 9, 1), date(2026, 10, 1))
        total = base + (nround(95 * k) if spike else 0)
        rows = []
        for j in range(total):
            idoso = spike and j >= base  # excedente vai para 60+
            src = s2_cohort_idoso if (idoso or r.random() < 0.45) else s2_cohort_geral
            src = _active_positions(ctx, src)
            if src.size == 0:
                continue
            bp = int(r.choice(src))
            pr = s2_procs[int(r.integers(0, len(s2_procs)))]
            prov = _prov_pick(cat, "clinica_medica", int(r.integers(0, 999)))
            rows.append(new_event_row(
                t=t, rng=r, id_beneficiario=int(cart.ids[bp]), id_prestador=prov[0],
                id_procedimento=pr["id"], id_especialidade=pr["espec_id"],
                id_regiao=int(cart.regiao_id[bp]), tipo_atendimento="internacao",
                custo=pr["custo"], nivel_preco=prov[2], cenario_tag=S2_TAG,
            ))
        return rows

    hooks.append(hook_internacoes)
    gaba.append(CenarioGabarito(
        codigo=S2_TAG, nome="Aumento de internações",
        competencia_alvo=S2_ALVO, dimensao="tipo_atendimento", chave_alvo="internacao",
        rotulo_alvo="internacao", efeito_esperado="frequencia",
        descricao="Set-Out/2026: internações ~+30-40% vs mês anterior, excedente concentrado "
                  "em beneficiários 60+.",
        params={"tag": S2_TAG, "k": k, "spike_meses": ["2026-09", "2026-10"],
                "faixa_alvo": "60+"},
    ))

    # ========================================================= S3 — PRESTADOR FORA DO PADRÃO
    prov_x_id, prov_x_reg, _ = _prov_pick(cat, "ortopedia", 0)
    s3_procs = [pidx["CIR-ARTJ"], pidx["IMG-RMJ"]]
    s3_cohort = cohort(idade0 >= 35, nround(3000 * k))
    S3_TAG = "s3_prestador_anomalo"
    S3_ALVO = date(2026, 6, 1)

    def hook_prestador_anomalo(ctx: dict) -> list[dict]:
        t, r = ctx["t"], ctx["rng"]
        pos = _active_positions(ctx, s3_cohort)
        if pos.size == 0:
            return []
        meses_desde_inicio = (t.year - cfg.inicio.year) * 12 + (t.month - cfg.inicio.month)
        ramp = 1.0 + 0.06 * meses_desde_inicio  # frequência crescente ao longo do tempo
        qtd = nround(14 * k * ramp)
        rows = []
        for j in range(qtd):
            bp = int(r.choice(pos))
            pr = s3_procs[j % 2]
            rows.append(new_event_row(
                t=t, rng=r, id_beneficiario=int(cart.ids[bp]), id_prestador=prov_x_id,
                id_procedimento=pr["id"], id_especialidade=pr["espec_id"],
                id_regiao=prov_x_reg, tipo_atendimento=pr["tipo"],
                custo=pr["custo"], nivel_preco=1.0, fator_custo=1.45,  # custo médio bem acima dos pares
                cenario_tag=S3_TAG,
            ))
        return rows

    hooks.append(hook_prestador_anomalo)
    gaba.append(CenarioGabarito(
        codigo=S3_TAG, nome="Prestador fora do padrão",
        competencia_alvo=S3_ALVO, dimensao="prestador", chave_alvo=str(prov_x_id),
        rotulo_alvo=None, efeito_esperado="misto",
        descricao="Um prestador de ortopedia com custo médio ~45% acima dos pares, frequência "
                  "crescente ao longo de 2026 e forte concentração em 2 procedimentos.",
        params={"tag": S3_TAG, "k": k, "id_prestador": prov_x_id,
                "procedimentos": [p["id"] for p in s3_procs]},
    ))

    # ================================================================= S4 — ALTO CUSTO
    s4_procs = [pidx["ONC-QT2"], pidx["IMB-INF"], pidx["NEF-HD"]]
    s4_cohort = cohort((idade0 >= 35) & (idade0 <= 72), nround(30 * k))
    S4_TAG = "s4_alto_custo"

    def hook_alto_custo(ctx: dict) -> list[dict]:
        t, r = ctx["t"], ctx["rng"]
        if t < date(2026, 3, 1):
            return []
        pos = _active_positions(ctx, s4_cohort)
        rows = []
        for bp in pos:
            pr = s4_procs[int(r.integers(0, len(s4_procs)))]
            sessoes = int(r.integers(1, 4))
            rows.append(new_event_row(
                t=t, rng=r, id_beneficiario=int(cart.ids[bp]),
                id_prestador=_prov_pick(cat, "oncologia", int(r.integers(0, 999)))[0],
                id_procedimento=pr["id"], id_especialidade=pr["espec_id"],
                id_regiao=int(cart.regiao_id[bp]), tipo_atendimento="terapia",
                custo=pr["custo"], nivel_preco=1.0, quantidade=sessoes, cenario_tag=S4_TAG,
            ))
        return rows

    hooks.append(hook_alto_custo)
    gaba.append(CenarioGabarito(
        codigo=S4_TAG, nome="Beneficiários de alto custo",
        competencia_alvo=date(2026, 6, 1), dimensao="beneficiario", chave_alvo=None,
        efeito_esperado="concentracao",
        descricao="~30 beneficiários (escala x k) com terapias de altíssimo custo a partir de "
                  "mar/2026, gerando forte concentração de despesa.",
        params={"tag": S4_TAG, "k": k, "n_beneficiarios": int(s4_cohort.size),
                "share_top1pct_min": 0.18},
    ))

    # ============================================================ S5 — SAZONALIDADE RESPIRATÓRIA
    s5_procs = [pidx["CON-PNE"], pidx["INT-PNM"], pidx["PS-PED"], pidx["PS-CLM"]]
    s5_cohort = cohort(np.ones(n, dtype=bool), nround(4000 * k))
    S5_TAG = "s5_sazonalidade_resp"

    def hook_sazonalidade(ctx: dict) -> list[dict]:
        t, r = ctx["t"], ctx["rng"]
        if t.month not in (6, 7, 8):
            return []
        pos = _active_positions(ctx, s5_cohort)
        if pos.size == 0:
            return []
        qtd = nround(110 * k)  # repete TODO inverno (2025 e 2026) -> padrão sazonal
        rows = []
        for _ in range(qtd):
            bp = int(r.choice(pos))
            pr = s5_procs[int(r.integers(0, len(s5_procs)))]
            rows.append(new_event_row(
                t=t, rng=r, id_beneficiario=int(cart.ids[bp]),
                id_prestador=_prov_pick(cat, "pneumologia", int(r.integers(0, 999)))[0],
                id_procedimento=pr["id"], id_especialidade=pr["espec_id"],
                id_regiao=int(cart.regiao_id[bp]), tipo_atendimento=pr["tipo"],
                custo=pr["custo"], nivel_preco=1.0, cenario_tag=S5_TAG,
            ))
        return rows

    hooks.append(hook_sazonalidade)
    gaba.append(CenarioGabarito(
        codigo=S5_TAG, nome="Sazonalidade respiratória de inverno",
        competencia_alvo=date(2026, 7, 1), dimensao="especialidade",
        chave_alvo=str(cat.espec_id["pneumologia"]), rotulo_alvo="Pneumologia",
        efeito_esperado="sazonal",
        descricao="Jun-Ago de 2025 E 2026: alta de atendimentos respiratórios. Por repetir nos "
                  "dois invernos, o motor deve classificar como variação sazonal esperada.",
        params={"tag": S5_TAG, "k": k, "meses": [6, 7, 8]},
    ))

    # ============================================================ S6 — PRONTO-SOCORRO RECORRENTE
    s6_procs = [pidx["PS-CLM"], pidx["PS-PED"], pidx["PS-ORT"]]
    s6_cohort = cohort(np.ones(n, dtype=bool), nround(480 * k))
    S6_TAG = "s6_ps_recorrente"

    def hook_ps_recorrente(ctx: dict) -> list[dict]:
        t, r = ctx["t"], ctx["rng"]
        pos = _active_positions(ctx, s6_cohort)
        rows = []
        for bp in pos:
            for _ in range(int(r.integers(3, 6))):  # 3-5 idas ao PS por mês (uso recorrente)
                pr = s6_procs[int(r.integers(0, len(s6_procs)))]
                rows.append(new_event_row(
                    t=t, rng=r, id_beneficiario=int(cart.ids[bp]),
                    id_prestador=_prov_pick(cat, "clinica_medica", int(r.integers(0, 999)))[0],
                    id_procedimento=pr["id"], id_especialidade=pr["espec_id"],
                    id_regiao=int(cart.regiao_id[bp]), tipo_atendimento="pronto_socorro",
                    custo=pr["custo"], nivel_preco=1.0, cenario_tag=S6_TAG,
                ))
        return rows

    hooks.append(hook_ps_recorrente)
    gaba.append(CenarioGabarito(
        codigo=S6_TAG, nome="Utilização recorrente de pronto atendimento",
        competencia_alvo=date(2026, 6, 1), dimensao="tipo_atendimento", chave_alvo="pronto_socorro",
        rotulo_alvo="pronto_socorro", efeito_esperado="frequencia",
        descricao="~480 beneficiários (x k) com uso recorrente de pronto-socorro todos os meses.",
        params={"tag": S6_TAG, "k": k, "n_beneficiarios": int(s6_cohort.size)},
    ))

    # ============================================================ S7 — CUSTO MÉDIO (preço)
    s7_proc = pidx["IMG-RM"]
    s7_cohort = cohort(idade0 >= 25, nround(3000 * k))
    S7_TAG = "s7_custo_medio"
    S7_ALVO = date(2026, 6, 1)

    def hook_custo_medio(ctx: dict) -> list[dict]:
        t, r = ctx["t"], ctx["rng"]
        pos = _active_positions(ctx, s7_cohort)
        if pos.size == 0:
            return []
        qtd = nround(130 * k)  # FREQUÊNCIA ESTÁVEL todos os meses
        # custo dá um degrau de +30% a partir de jun/2026
        fator = 1.30 if t >= S7_ALVO else 1.0
        rows = []
        for _ in range(qtd):
            bp = int(r.choice(pos))
            rows.append(new_event_row(
                t=t, rng=r, id_beneficiario=int(cart.ids[bp]),
                id_prestador=_prov_pick(cat, "radiologia", int(r.integers(0, 999)))[0],
                id_procedimento=s7_proc["id"], id_especialidade=s7_proc["espec_id"],
                id_regiao=int(cart.regiao_id[bp]), tipo_atendimento="exame",
                custo=s7_proc["custo"], nivel_preco=1.0, fator_custo=fator, cenario_tag=S7_TAG,
            ))
        return rows

    hooks.append(hook_custo_medio)
    gaba.append(CenarioGabarito(
        codigo=S7_TAG, nome="Aumento por custo médio (preço)",
        competencia_alvo=S7_ALVO, dimensao="procedimento", chave_alvo=str(s7_proc["id"]),
        rotulo_alvo="Ressonância magnética", efeito_esperado="custo_medio",
        descricao="Ressonância magnética: frequência estável todos os meses, custo médio com "
                  "degrau de +30% a partir de jun/2026.",
        params={"tag": S7_TAG, "k": k, "degrau_mes": "2026-06", "fator_custo": 1.30},
    ))

    # ============================================================ S8 — MELHORA / REDUÇÃO
    s8_proc = pidx["FIS-SES"]
    s8_cohort = cohort(idade0 >= 20, nround(6000 * k))
    S8_TAG = "s8_melhora_fisioterapia"
    S8_ALVO = date(2026, 10, 1)

    def hook_melhora(ctx: dict) -> list[dict]:
        t, r = ctx["t"], ctx["rng"]
        pos = _active_positions(ctx, s8_cohort)
        if pos.size == 0:
            return []
        base = nround(360 * k)
        qtd = nround(base * 0.5) if t >= S8_ALVO else base  # programa de gestão reduz frequência
        rows = []
        for _ in range(qtd):
            bp = int(r.choice(pos))
            rows.append(new_event_row(
                t=t, rng=r, id_beneficiario=int(cart.ids[bp]),
                id_prestador=_prov_pick(cat, "fisioterapia", int(r.integers(0, 999)))[0],
                id_procedimento=s8_proc["id"], id_especialidade=s8_proc["espec_id"],
                id_regiao=int(cart.regiao_id[bp]), tipo_atendimento="terapia",
                custo=s8_proc["custo"], nivel_preco=1.0, quantidade=int(r.integers(1, 4)),
                cenario_tag=S8_TAG,
            ))
        return rows

    hooks.append(hook_melhora)
    gaba.append(CenarioGabarito(
        codigo=S8_TAG, nome="Melhora: redução de despesa em fisioterapia",
        competencia_alvo=S8_ALVO, dimensao="procedimento",
        chave_alvo=str(s8_proc["id"]), rotulo_alvo="Sessão de fisioterapia",
        efeito_esperado="frequencia",
        descricao="A partir de out/2026 um programa de gestão reduz ~50% a frequência de "
                  "fisioterapia, derrubando a despesa da especialidade (insight positivo).",
        params={"tag": S8_TAG, "k": k, "direcao": "reducao", "mes": "2026-10"},
    ))

    # ============================================================ S9 — RECEITA ESTAGNADA
    S9_TAG = "s9_receita_estagnada"
    supr_reajuste = {2026}

    owned_proc_ids: set[int] = {
        cat_proc["id"],       # S1  CIR-CAT
        s7_proc["id"],        # S7  IMG-RM
        s8_proc["id"],        # S8  FIS-SES
    }
    blocked_prestador_ids: set[int] = {prov_x_id}  # S3 — só recebe eventos do hook

    gaba.append(CenarioGabarito(
        codigo=S9_TAG, nome="Sinistralidade sobe por comportamento da receita",
        competencia_alvo=date(2026, 5, 1), dimensao=None, chave_alvo=None,
        efeito_esperado="receita",
        descricao="O reajuste anual de maio/2026 é suprimido: a receita per capita fica "
                  "estagnada enquanto a despesa cresce, elevando a sinistralidade pela via do "
                  "denominador.",
        params={"tag": S9_TAG, "ano_sem_reajuste": 2026},
    ))

    # ================================================== S10-S13 — COMPOSIÇÃO FINANCEIRA
    # Não precisam de hooks de eventos: atuam sobre a taxa de glosa / percentual de
    # coparticipação / receita de competências específicas (Etapa B da v1.1).
    glosa_mult_por_mes: dict[date, float] = {date(2026, 2, 1): 3.4}          # S10 — Cenário A
    copart_mult_por_mes: dict[date, float] = {date(2026, 5, 1): 3.6}        # S11 — Cenário B
    glosa_mult_por_mes[date(2026, 10, 1)] = 2.2                              # S12 — Cenário C
    copart_mult_por_mes[date(2026, 10, 1)] = 2.2                            # S12 — Cenário C
    glosa_mult_por_mes[date(2026, 12, 1)] = 1.35                             # S13 — Cenário D
    receita_ajuste_pontual: dict[date, float] = {date(2026, 12, 1): 0.85}   # S13 — Cenário D

    gaba.append(CenarioGabarito(
        codigo="s10_glosa_aumenta", nome="Melhora da despesa líquida por aumento de glosa",
        competencia_alvo=date(2026, 2, 1), dimensao=None, chave_alvo=None,
        efeito_esperado="glosa",
        descricao="Fev/2026: taxa de glosa sobe fortemente (~3,4x). O motor deve atribuir a "
                  "melhora da despesa líquida predominantemente às glosas (maior efeito "
                  "entre os componentes de despesa).",
        params={"mes": "2026-02", "glosa_mult": 3.4},
    ))
    gaba.append(CenarioGabarito(
        codigo="s11_coparticipacao_aumenta", nome="Despesa líquida cai por aumento de coparticipação",
        competencia_alvo=date(2026, 5, 1), dimensao=None, chave_alvo=None,
        efeito_esperado="coparticipacao",
        descricao="Mai/2026: percentual de coparticipação dos planos elegíveis sobe "
                  "fortemente (~3,6x). O motor deve atribuir o efeito predominantemente à "
                  "coparticipação (maior efeito entre os componentes de despesa).",
        params={"mes": "2026-05", "copart_mult": 3.6},
    ))
    gaba.append(CenarioGabarito(
        codigo="s12_glosa_copart_combinado", nome="Efeito combinado de glosa e coparticipação",
        competencia_alvo=date(2026, 10, 1), dimensao=None, chave_alvo=None,
        efeito_esperado="misto_financeiro",
        descricao="Out/2026: glosa e coparticipação sobem juntas (~2,2x cada). Líquida cai "
                  "por efeito combinado — glosa+coparticipação juntas devem superar o "
                  "efeito da despesa bruta.",
        params={"mes": "2026-10", "glosa_mult": 2.2, "copart_mult": 2.2},
    ))
    gaba.append(CenarioGabarito(
        codigo="s13_receita_cai_mais", nome="Despesa cai mas receita cai mais — sinistralidade piora",
        competencia_alvo=date(2026, 12, 1), dimensao=None, chave_alvo=None,
        efeito_esperado="receita",
        descricao="Dez/2026: despesa líquida cai (glosa levemente maior), mas um ajuste "
                  "pontual de receita (-15%) faz a sinistralidade líquida piorar mesmo com "
                  "despesa em queda — efeito receita deve dominar a decomposição.",
        params={"mes": "2026-12", "glosa_mult": 1.35, "receita_mult": 0.85},
    ))

    return (
        hooks, gaba, supr_reajuste, owned_proc_ids, blocked_prestador_ids,
        glosa_mult_por_mes, copart_mult_por_mes, receita_ajuste_pontual,
    )
