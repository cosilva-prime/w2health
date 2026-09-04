"""Motor de avaliação de alertas configurados (v1.1, Etapa C).

Distinção conceitual OBRIGATÓRIA e implementada como módulos separados:
  - `insights.py`  -> INSIGHT AUTOMÁTICO: achado do motor, sem configuração do usuário.
  - `alerts.py`    -> ALERTA CONFIGURADO: regra definida pelo usuário (`regras_alerta`),
                      avaliada contra os dados reais/sintéticos do período. Uma regra só
                      dispara quando o indicador calculado realmente cruza o limite —
                      nunca um alerta "fake".
"""

from __future__ import annotations

import operator
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.analytics import indicadores
from app.repositories import config_repo

_OPERADORES = {
    ">=": operator.ge, ">": operator.gt,
    "<=": operator.le, "<": operator.lt,
    "==": operator.eq,
}

_DEEP_LINK_ROTA = {
    "beneficiario": "/beneficiarios/{id}",
    "prestador": "/prestadores/{id}",
    "procedimento": "/sinistralidade",
    "plano": "/sinistralidade",
    "contrato": "/sinistralidade",
    "financeiro": "/sinistralidade",
}


@dataclass
class Alerta:
    regra_id: int
    regra_nome: str
    entidade: str
    entidade_id: str
    rotulo: str
    indicador: str
    indicador_rotulo: str
    unidade: str
    valor_observado: float
    operador: str
    limite: float
    severidade: str
    competencia: str
    deep_link: dict

    def as_dict(self) -> dict:
        return {
            "regra_id": self.regra_id,
            "regra_nome": self.regra_nome,
            "entidade": self.entidade,
            "entidade_id": self.entidade_id,
            "rotulo": self.rotulo,
            "indicador": self.indicador,
            "indicador_rotulo": self.indicador_rotulo,
            "unidade": self.unidade,
            "valor_observado": round(self.valor_observado, 2),
            "operador": self.operador,
            "limite": self.limite,
            "severidade": self.severidade,
            "competencia": self.competencia,
            "deep_link": self.deep_link,
        }


def _deep_link(entidade: str, entidade_id) -> dict:
    rota = _DEEP_LINK_ROTA.get(entidade, "/insights")
    if "{id}" in rota:
        return {"rota": rota.format(id=entidade_id), "params": {}}
    return {"rota": rota, "params": {"dimensao": entidade, "chave": str(entidade_id)}}


def avaliar_regras(session: Session, competencia: date, comparacao: str = "mes_anterior") -> list[Alerta]:
    """Avalia todas as regras ativas contra os dados do período. Nunca gera alerta sem
    o indicador realmente cruzar o limite configurado."""
    regras = config_repo.listar(session, apenas_ativas=True)
    alertas: list[Alerta] = []

    for regra in regras:
        definicao = indicadores.obter(regra.entidade, regra.indicador)
        if definicao is None:
            continue  # indicador desconhecido/desatualizado — regra ignorada, não quebra
        op = _OPERADORES.get(regra.operador)
        if op is None:
            continue
        try:
            valores = definicao.funcao(session, competencia, comparacao, regra.escopo or {})
        except Exception:  # noqa: BLE001 - uma regra malformada não derruba as demais
            continue
        for v in valores:
            if op(v["valor"], regra.limite):
                alertas.append(
                    Alerta(
                        regra_id=regra.id, regra_nome=regra.nome, entidade=regra.entidade,
                        entidade_id=str(v["entidade_id"]), rotulo=v["rotulo"],
                        indicador=regra.indicador, indicador_rotulo=definicao.rotulo,
                        unidade=definicao.unidade, valor_observado=v["valor"],
                        operador=regra.operador, limite=regra.limite, severidade=regra.severidade,
                        competencia=competencia.isoformat(),
                        deep_link=_deep_link(regra.entidade, v["entidade_id"]),
                    )
                )

    ordem_severidade = {"critica": 0, "atencao": 1, "informativo": 2}
    alertas.sort(key=lambda a: (ordem_severidade.get(a.severidade, 9), -abs(a.valor_observado)))
    return alertas
