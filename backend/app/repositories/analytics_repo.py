"""Consultas da camada analítica. Retornam estruturas Python simples (dicts/listas)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session


def competencias(session: Session) -> list[date]:
    rows = session.execute(
        text("SELECT competencia FROM agg_sinistralidade_competencia ORDER BY competencia")
    ).scalars().all()
    return list(rows)


# Colunas comuns às consultas de sinistralidade mensal. `despesa`/`sinistralidade` são
# ALIASES de despesa_liquida/sinistralidade_liquida — a convenção oficial do MVP para o
# KPI principal (ver docs/DATA_MODEL.md). Nenhuma coluna redundante é criada: o alias
# só existe na consulta, não no banco.
_COLUNAS_SINISTRALIDADE = """
    competencia, receita,
    despesa_liquida AS despesa, sinistralidade_liquida AS sinistralidade,
    despesa_bruta, glosas, coparticipacao, despesa_liquida,
    sinistralidade_bruta, sinistralidade_liquida,
    beneficiarios_ativos, exposicao_beneficiario_mes, eventos, custo_pmpm,
    receita_media_beneficiario
"""


def serie_sinistralidade(session: Session) -> list[dict]:
    rows = session.execute(
        text(
            f"SELECT {_COLUNAS_SINISTRALIDADE} FROM agg_sinistralidade_competencia "
            "ORDER BY competencia"
        )
    ).mappings().all()
    return [dict(r) for r in rows]


def sinistralidade_mes(session: Session, competencia: date) -> dict | None:
    r = session.execute(
        text(
            f"SELECT {_COLUNAS_SINISTRALIDADE} FROM agg_sinistralidade_competencia "
            "WHERE competencia = :c"
        ),
        {"c": competencia},
    ).mappings().first()
    return dict(r) if r else None


def dimensao_mes(session: Session, competencia: date, dimensao: str) -> dict[str, dict]:
    """chave -> métricas do agregado (competência x dimensão)."""
    rows = session.execute(
        text(
            """
            SELECT chave, rotulo, despesa, eventos, quantidade, beneficiarios,
                   custo_medio, freq_por_mil
            FROM agg_competencia_dimensao
            WHERE competencia = :c AND dimensao = :d
            """
        ),
        {"c": competencia, "d": dimensao},
    ).mappings().all()
    return {r["chave"]: dict(r) for r in rows}


def dimensao_serie(session: Session, dimensao: str, chave: str) -> list[dict]:
    rows = session.execute(
        text(
            """
            SELECT competencia, rotulo, despesa, eventos, quantidade, beneficiarios,
                   custo_medio, freq_por_mil
            FROM agg_competencia_dimensao
            WHERE dimensao = :d AND chave = :k ORDER BY competencia
            """
        ),
        {"d": dimensao, "k": chave},
    ).mappings().all()
    return [dict(r) for r in rows]


def prestadores_mes(session: Session, competencia: date) -> list[dict]:
    rows = session.execute(
        text(
            """
            SELECT a.id_prestador, p.nome_ficticio AS nome, p.tipo_prestador AS tipo,
                   r.cidade || '/' || r.uf AS regiao, e.nome AS especialidade_principal,
                   a.despesa, a.eventos, a.beneficiarios, a.custo_medio, a.participacao,
                   a.procedimento_top_id, a.procedimento_top_share
            FROM agg_prestador_competencia a
            JOIN prestadores p ON p.id = a.id_prestador
            JOIN regioes r ON r.id = p.id_regiao
            JOIN especialidades e ON e.id = p.id_especialidade_principal
            WHERE a.competencia = :c
            """
        ),
        {"c": competencia},
    ).mappings().all()
    return [dict(r) for r in rows]


def prestador_serie(session: Session, id_prestador: int) -> list[dict]:
    rows = session.execute(
        text(
            """
            SELECT competencia, despesa, eventos, beneficiarios, custo_medio, participacao,
                   procedimento_top_id, procedimento_top_share
            FROM agg_prestador_competencia WHERE id_prestador = :p ORDER BY competencia
            """
        ),
        {"p": id_prestador},
    ).mappings().all()
    return [dict(r) for r in rows]


def prestador_info(session: Session, id_prestador: int) -> dict | None:
    r = session.execute(
        text(
            """
            SELECT p.id, p.nome_ficticio AS nome, p.tipo_prestador AS tipo,
                   p.nivel_preco, r.cidade || '/' || r.uf AS regiao,
                   e.id AS id_especialidade_principal, e.nome AS especialidade_principal
            FROM prestadores p
            JOIN regioes r ON r.id = p.id_regiao
            JOIN especialidades e ON e.id = p.id_especialidade_principal
            WHERE p.id = :p
            """
        ),
        {"p": id_prestador},
    ).mappings().first()
    return dict(r) if r else None


def prestador_top_procedimentos(
    session: Session, id_prestador: int, competencia: date, limit: int = 8
) -> list[dict]:
    rows = session.execute(
        text(
            """
            SELECT pr.id, pr.descricao, pr.grupo_procedimento,
                   COUNT(*) AS eventos, SUM(e.valor_pago) AS despesa,
                   AVG(e.valor_pago) AS custo_medio
            FROM eventos_assistenciais e
            JOIN procedimentos pr ON pr.id = e.id_procedimento
            WHERE e.id_prestador = :p AND e.competencia = :c
            GROUP BY pr.id, pr.descricao, pr.grupo_procedimento
            ORDER BY despesa DESC LIMIT :lim
            """
        ),
        {"p": id_prestador, "c": competencia, "lim": limit},
    ).mappings().all()
    return [dict(r) for r in rows]


def prestador_peers_mes(
    session: Session, competencia: date, id_especialidade_principal: int
) -> list[dict]:
    """Métricas do mês para todos os prestadores com a mesma especialidade principal."""
    rows = session.execute(
        text(
            """
            SELECT a.id_prestador, p.tipo_prestador AS tipo,
                   a.despesa, a.eventos, a.beneficiarios, a.custo_medio,
                   a.procedimento_top_share
            FROM agg_prestador_competencia a
            JOIN prestadores p ON p.id = a.id_prestador
            WHERE a.competencia = :c AND p.id_especialidade_principal = :e
            """
        ),
        {"c": competencia, "e": id_especialidade_principal},
    ).mappings().all()
    return [dict(r) for r in rows]


def beneficiario_serie(session: Session, id_beneficiario: int) -> list[dict]:
    rows = session.execute(
        text(
            """
            SELECT competencia, despesa, eventos
            FROM agg_beneficiario_competencia WHERE id_beneficiario = :b ORDER BY competencia
            """
        ),
        {"b": id_beneficiario},
    ).mappings().all()
    return [dict(r) for r in rows]


def beneficiarios_top(
    session: Session, competencia: date, limit: int, offset: int,
    faixa_etaria: str | None = None, sexo: str | None = None, id_plano: int | None = None,
) -> tuple[list[dict], int]:
    where = ["a.competencia = :c"]
    params: dict = {"c": competencia, "lim": limit, "off": offset}
    if faixa_etaria:
        where.append("b.faixa_etaria = :fe")
        params["fe"] = faixa_etaria
    if sexo:
        where.append("b.sexo = :sx")
        params["sx"] = sexo
    if id_plano:
        where.append("b.id_plano = :pl")
        params["pl"] = id_plano
    w = " AND ".join(where)
    total = session.execute(
        text(
            f"SELECT COUNT(*) FROM agg_beneficiario_competencia a "
            f"JOIN beneficiarios b ON b.id = a.id_beneficiario WHERE {w}"
        ),
        params,
    ).scalar_one()
    rows = session.execute(
        text(
            f"""
            SELECT b.id, b.codigo, b.sexo, b.faixa_etaria,
                   r.cidade || '/' || r.uf AS regiao, pl.nome AS plano,
                   a.despesa, a.eventos
            FROM agg_beneficiario_competencia a
            JOIN beneficiarios b ON b.id = a.id_beneficiario
            JOIN regioes r ON r.id = b.id_regiao
            JOIN planos pl ON pl.id = b.id_plano
            WHERE {w}
            ORDER BY a.despesa DESC
            LIMIT :lim OFFSET :off
            """
        ),
        params,
    ).mappings().all()
    return [dict(r) for r in rows], int(total)


def beneficiario_info(session: Session, id_beneficiario: int) -> dict | None:
    r = session.execute(
        text(
            """
            SELECT b.id, b.codigo, b.sexo, b.faixa_etaria, b.data_nascimento,
                   b.data_adesao, b.status,
                   r.cidade || '/' || r.uf AS regiao, r.macrorregiao,
                   pl.nome AS plano, ct.nome AS contrato
            FROM beneficiarios b
            JOIN regioes r ON r.id = b.id_regiao
            JOIN planos pl ON pl.id = b.id_plano
            JOIN contratos ct ON ct.id = b.id_contrato
            WHERE b.id = :b
            """
        ),
        {"b": id_beneficiario},
    ).mappings().first()
    return dict(r) if r else None


def beneficiario_por_codigo(session: Session, codigo: str) -> int | None:
    return session.execute(
        text("SELECT id FROM beneficiarios WHERE codigo = :c"), {"c": codigo}
    ).scalar_one_or_none()


def beneficiario_eventos(session: Session, id_beneficiario: int) -> list[dict]:
    rows = session.execute(
        text(
            """
            SELECT e.id, e.data_evento, e.competencia, e.tipo_atendimento, e.quantidade,
                   e.valor_apresentado, e.valor_glosado, e.valor_pago,
                   p.descricao AS procedimento, p.grupo_procedimento,
                   es.nome AS especialidade, pr.nome_ficticio AS prestador,
                   d.descricao AS diagnostico
            FROM eventos_assistenciais e
            JOIN procedimentos p ON p.id = e.id_procedimento
            JOIN especialidades es ON es.id = e.id_especialidade
            JOIN prestadores pr ON pr.id = e.id_prestador
            LEFT JOIN diagnosticos d ON d.id = e.id_diagnostico
            WHERE e.id_beneficiario = :b
            ORDER BY e.data_evento
            """
        ),
        {"b": id_beneficiario},
    ).mappings().all()
    return [dict(r) for r in rows]


def despesa_por_beneficiario(session: Session, competencia: date) -> list[float]:
    rows = session.execute(
        text(
            "SELECT despesa FROM agg_beneficiario_competencia WHERE competencia = :c"
        ),
        {"c": competencia},
    ).scalars().all()
    return [float(x) for x in rows]


# Cláusula WHERE (parametrizada) para filtrar eventos por dimensão/chave. Compartilhada
# por `eventos_da_categoria` e pelas consultas de coortes (Etapa A da v1.1).
_FILTRO_DIMENSAO: dict[str, str] = {
    "especialidade": "e.id_especialidade = :kv",
    "procedimento": "e.id_procedimento = :kv",
    "prestador": "e.id_prestador = :kv",
    "regiao": "e.id_regiao = :kv",
    "tipo_atendimento": "e.tipo_atendimento = :kt",
    "grupo_despesa": "proc.grupo_procedimento = :kt",
    "faixa_etaria": "b.faixa_etaria = :kt",
    "sexo": "b.sexo = :kt",
    "plano": "b.id_plano = :kv",
    "contrato": "b.id_contrato = :kv",
}


def _filtro_dimensao(dimensao: str, chave: str) -> tuple[str, dict]:
    """Retorna (cláusula SQL, params) para filtrar eventos por (dimensao, chave)."""
    clausula = _FILTRO_DIMENSAO[dimensao]
    params = {"kv": int(chave)} if ":kv" in clausula else {"kt": chave}
    return clausula, params


def eventos_da_categoria(
    session: Session, competencia: date, dimensao: str, chave: str,
    agrupar_por: str = "prestador", limit: int = 10,
) -> list[dict]:
    """Top `agrupar_por` (prestador|beneficiario) dentro de uma célula dimensão/chave/mês.

    Usado no drill-down "onde investigar primeiro".
    """
    filtro_dim, fparams = _filtro_dimensao(dimensao, chave)
    params: dict = {"c": competencia, "lim": limit, **fparams}

    if agrupar_por == "beneficiario":
        sel = "b.id AS id, b.codigo AS rotulo"
        grp = "b.id, b.codigo"
    else:
        sel = "prov.id AS id, prov.nome_ficticio AS rotulo"
        grp = "prov.id, prov.nome_ficticio"

    rows = session.execute(
        text(
            f"""
            SELECT {sel}, COUNT(*) AS eventos, SUM(e.valor_pago) AS despesa,
                   AVG(e.valor_pago) AS custo_medio
            FROM eventos_assistenciais e
            JOIN procedimentos proc ON proc.id = e.id_procedimento
            JOIN prestadores prov ON prov.id = e.id_prestador
            JOIN beneficiarios b ON b.id = e.id_beneficiario
            WHERE e.competencia = :c AND {filtro_dim}
            GROUP BY {grp}
            ORDER BY despesa DESC
            LIMIT :lim
            """
        ),
        params,
    ).mappings().all()
    return [dict(r) for r in rows]


def beneficiarios_da_categoria(
    session: Session, competencia: date, dimensao: str, chave: str
) -> dict[int, dict]:
    """id_beneficiario -> {despesa, eventos} para TODOS os beneficiários de uma célula
    dimensão/chave/mês (sem limite — base da análise de coortes, Etapa A)."""
    filtro_dim, fparams = _filtro_dimensao(dimensao, chave)
    rows = session.execute(
        text(
            f"""
            SELECT e.id_beneficiario AS id, SUM(e.valor_pago) AS despesa, COUNT(*) AS eventos
            FROM eventos_assistenciais e
            JOIN procedimentos proc ON proc.id = e.id_procedimento
            JOIN beneficiarios b ON b.id = e.id_beneficiario
            WHERE e.competencia = :c AND {filtro_dim}
            GROUP BY e.id_beneficiario
            """
        ),
        {"c": competencia, **fparams},
    ).mappings().all()
    return {
        int(r["id"]): {"despesa": float(r["despesa"]), "eventos": int(r["eventos"])} for r in rows
    }


def beneficiarios_status_bulk(session: Session, ids: list[int]) -> dict[int, dict]:
    """Metadados de carteira em lote — status, saída, adesão, perfil demográfico."""
    if not ids:
        return {}
    rows = session.execute(
        text(
            """
            SELECT id, codigo, status, data_saida, data_adesao, faixa_etaria, sexo, id_contrato
            FROM beneficiarios WHERE id = ANY(:ids)
            """
        ),
        {"ids": ids},
    ).mappings().all()
    return {int(r["id"]): dict(r) for r in rows}


def prestadores_por_beneficiario_na_categoria(
    session: Session, competencia: date, dimensao: str, chave: str, ids: list[int]
) -> dict[int, set[int]]:
    """id_beneficiario -> conjunto de prestadores usados, dentro da célula/mês (para
    detectar troca de prestador entre dois meses)."""
    if not ids:
        return {}
    filtro_dim, fparams = _filtro_dimensao(dimensao, chave)
    rows = session.execute(
        text(
            f"""
            SELECT DISTINCT e.id_beneficiario AS id, e.id_prestador AS id_prestador
            FROM eventos_assistenciais e
            JOIN procedimentos proc ON proc.id = e.id_procedimento
            JOIN beneficiarios b ON b.id = e.id_beneficiario
            WHERE e.competencia = :c AND {filtro_dim} AND e.id_beneficiario = ANY(:ids)
            """
        ),
        {"c": competencia, "ids": ids, **fparams},
    ).mappings().all()
    out: dict[int, set[int]] = {}
    for r in rows:
        out.setdefault(int(r["id"]), set()).add(int(r["id_prestador"]))
    return out


def perfil_utilizacao_despesa(
    session: Session, competencia: date, dimensao: str, chave: str, ids: list[int]
) -> dict[str, float]:
    """Despesa (na célula/mês, restrita a `ids`) somada por perfil_utilizacao do
    procedimento — 'pontual' | 'recorrente' | 'variavel'. Apoia a hipótese de conclusão
    de episódio pontual (nunca usada sozinha para afirmar causalidade)."""
    if not ids:
        return {}
    filtro_dim, fparams = _filtro_dimensao(dimensao, chave)
    rows = session.execute(
        text(
            f"""
            SELECT proc.perfil_utilizacao AS perfil, SUM(e.valor_pago) AS despesa
            FROM eventos_assistenciais e
            JOIN procedimentos proc ON proc.id = e.id_procedimento
            JOIN beneficiarios b ON b.id = e.id_beneficiario
            WHERE e.competencia = :c AND {filtro_dim} AND e.id_beneficiario = ANY(:ids)
            GROUP BY proc.perfil_utilizacao
            """
        ),
        {"c": competencia, "ids": ids, **fparams},
    ).mappings().all()
    return {r["perfil"]: float(r["despesa"]) for r in rows}


def procedimentos_mes_detalhe(session: Session, competencia: date) -> list[dict]:
    """Por procedimento no mês: eventos, despesa, custo médio + chaves de agrupamento
    (especialidade, grupo). Base da decomposição correta de fatores coesos."""
    rows = session.execute(
        text(
            """
            SELECT e.id_procedimento AS id,
                   pr.id_especialidade::text AS especialidade,
                   pr.grupo_procedimento AS grupo_despesa,
                   pr.descricao AS rotulo,
                   COUNT(*) AS eventos,
                   SUM(e.valor_pago) AS despesa
            FROM eventos_assistenciais e
            JOIN procedimentos pr ON pr.id = e.id_procedimento
            WHERE e.competencia = :c
            GROUP BY e.id_procedimento, pr.id_especialidade, pr.grupo_procedimento, pr.descricao
            """
        ),
        {"c": competencia},
    ).mappings().all()
    return [dict(r) for r in rows]


def beneficiarios_despesa_mes(session: Session, competencia: date) -> dict[int, dict]:
    """id_beneficiario -> {despesa, eventos, codigo} para TODOS os beneficiários no mês.

    Base para os indicadores de alerta de beneficiário (Etapa C da v1.1).
    """
    rows = session.execute(
        text(
            """
            SELECT a.id_beneficiario AS id, a.despesa, a.eventos, b.codigo
            FROM agg_beneficiario_competencia a
            JOIN beneficiarios b ON b.id = a.id_beneficiario
            WHERE a.competencia = :c
            """
        ),
        {"c": competencia},
    ).mappings().all()
    return {
        int(r["id"]): {
            "despesa": float(r["despesa"]), "eventos": r["eventos"], "codigo": r["codigo"],
        }
        for r in rows
    }


def planos_sinistralidade_mes(session: Session, competencia: date) -> list[dict]:
    """Sinistralidade por plano (receita já é nativamente por competência × plano)."""
    rows = session.execute(
        text(
            """
            SELECT pl.id, pl.nome AS rotulo,
                   COALESCE(r.receita, 0) AS receita,
                   COALESCE(d.despesa, 0) AS despesa,
                   COALESCE(v.vidas, 0) AS vidas
            FROM planos pl
            LEFT JOIN receitas r ON r.id_plano = pl.id AND r.competencia = :c
            LEFT JOIN (
                SELECT b.id_plano, SUM(e.valor_pago) AS despesa
                FROM eventos_assistenciais e JOIN beneficiarios b ON b.id = e.id_beneficiario
                WHERE e.competencia = :c GROUP BY b.id_plano
            ) d ON d.id_plano = pl.id
            LEFT JOIN (
                SELECT id_plano, COUNT(*) AS vidas FROM beneficiarios
                WHERE status = 'ativo' GROUP BY id_plano
            ) v ON v.id_plano = pl.id
            """
        ),
        {"c": competencia},
    ).mappings().all()
    out = []
    for r in rows:
        receita = float(r["receita"])
        despesa = float(r["despesa"])
        sin = despesa / receita * 100 if receita > 0 else 0.0
        out.append({"id": r["id"], "rotulo": r["rotulo"], "receita": receita,
                     "despesa": despesa, "sinistralidade": sin, "vidas": r["vidas"]})
    return out


def contratos_vidas_mes(session: Session) -> dict[int, dict]:
    """id_contrato -> {rotulo, vidas ativas}. Sem receita própria (ver docs/V1.1.md)."""
    rows = session.execute(
        text(
            """
            SELECT ct.id, ct.nome AS rotulo, COUNT(b.id) AS vidas
            FROM contratos ct
            LEFT JOIN beneficiarios b ON b.id_contrato = ct.id AND b.status = 'ativo'
            GROUP BY ct.id, ct.nome
            """
        )
    ).mappings().all()
    return {int(r["id"]): {"rotulo": r["rotulo"], "vidas": r["vidas"]} for r in rows}


def gabarito(session: Session) -> list[dict]:
    rows = session.execute(
        text(
            """
            SELECT codigo, nome, competencia_alvo, dimensao, chave_alvo, rotulo_alvo,
                   efeito_esperado, descricao, params
            FROM cenarios_gabarito ORDER BY codigo
            """
        )
    ).mappings().all()
    return [dict(r) for r in rows]
