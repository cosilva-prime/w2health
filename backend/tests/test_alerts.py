"""Testes de configuração de insights e alertas (v1.1, Etapa C).

Cobrem: CRUD de regras, catálogo fechado de indicadores, e que um alerta só é emitido
quando o indicador realmente cruza o limite configurado (nunca um alerta "fake").
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.analytics import alerts, indicadores
from app.db.session import get_db
from app.main import create_app
from app.models import RegraAlerta

pytestmark = pytest.mark.scenarios


@pytest.fixture
def api(seeded_sessionmaker) -> TestClient:
    app = create_app()

    def _get_db():
        s: Session = seeded_sessionmaker()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _get_db
    return TestClient(app)


# -------------------------------------------------------------------------- catálogo
def test_catalogo_cobre_todas_as_entidades():
    entidades = {d.entidade for d in indicadores.CATALOGO.values()}
    esperado = {"beneficiario", "prestador", "procedimento", "plano", "contrato", "financeiro"}
    assert entidades == esperado


def test_catalogo_indicadores_endpoint(api):
    r = api.get("/api/config/indicadores")
    assert r.status_code == 200
    itens = r.json()["itens"]
    assert "beneficiario" in itens and "prestador" in itens
    chaves_beneficiario = {i["chave"] for i in itens["beneficiario"]}
    assert "participacao_variacao" in chaves_beneficiario


# -------------------------------------------------------------------------------- CRUD
def test_crud_regra_alerta(api):
    payload = {
        "nome": "Regra de teste", "entidade": "prestador", "indicador": "crescimento_despesa",
        "operador": ">=", "limite": 25.0, "severidade": "atencao",
    }
    r = api.post("/api/config/regras-alerta", json=payload)
    assert r.status_code == 201
    regra = r.json()
    rid = regra["id"]
    assert regra["ativo"] is True

    r = api.get(f"/api/config/regras-alerta/{rid}")
    assert r.status_code == 200 and r.json()["nome"] == "Regra de teste"

    r = api.put(f"/api/config/regras-alerta/{rid}", json={"limite": 40.0, "ativo": False})
    assert r.status_code == 200
    assert r.json()["limite"] == 40.0 and r.json()["ativo"] is False

    r = api.delete(f"/api/config/regras-alerta/{rid}")
    assert r.status_code == 204
    assert api.get(f"/api/config/regras-alerta/{rid}").status_code == 404


def test_criar_regra_indicador_invalido_422(api):
    r = api.post(
        "/api/config/regras-alerta",
        json={"nome": "x", "entidade": "beneficiario", "indicador": "nao_existe",
              "operador": ">=", "limite": 1, "severidade": "critica"},
    )
    assert r.status_code == 422


def test_criar_regra_payload_invalido_422(api):
    r = api.post(
        "/api/config/regras-alerta",
        json={"nome": "x", "entidade": "planeta", "indicador": "y", "operador": ">=",
              "limite": 1, "severidade": "critica"},
    )
    assert r.status_code == 422


# --------------------------------------------------------------- avaliação (não-fake)
def test_regra_nao_dispara_quando_limite_nao_atingido(db):
    regra = RegraAlerta(
        nome="Beneficiário de alto impacto (exemplo do enunciado)", entidade="beneficiario",
        indicador="participacao_variacao", operador=">=", limite=50.0, severidade="critica",
    )
    db.add(regra)
    db.commit()
    resultado = alerts.avaliar_regras(db, date(2026, 6, 1), "mes_anterior")
    assert all(a.regra_id != regra.id for a in resultado), (
        "em uma carteira de milhares de beneficiários, 50% de participação na variação "
        "não deveria ser atingido por ninguém — o alerta não pode disparar sem evidência"
    )


def test_regra_dispara_com_limite_calibrado_para_a_carteira(db):
    """Mesmo indicador do teste acima, com limite calibrado para a escala real dos
    dados — deve disparar com valores genuinamente calculados."""
    regra = RegraAlerta(
        nome="Beneficiário de alto impacto (calibrado)", entidade="beneficiario",
        indicador="participacao_variacao", operador=">=", limite=0.3, severidade="critica",
    )
    db.add(regra)
    db.commit()
    todas = alerts.avaliar_regras(db, date(2026, 6, 1), "mes_anterior")
    resultado = [a for a in todas if a.regra_id == regra.id]
    assert resultado, "esperava ao menos um alerta com limite calibrado para a carteira"
    for a in resultado:
        assert a.valor_observado >= regra.limite
        assert a.rotulo.startswith("BEN-")


def test_regra_prestador_crescimento_dispara(db):
    regra = RegraAlerta(
        nome="Prestador com crescimento relevante", entidade="prestador",
        indicador="crescimento_despesa", operador=">=", limite=30.0, severidade="atencao",
    )
    db.add(regra)
    db.commit()
    todas = alerts.avaliar_regras(db, date(2026, 6, 1), "mes_anterior")
    resultado = [a for a in todas if a.regra_id == regra.id]
    assert resultado
    assert all(a.valor_observado >= 30.0 for a in resultado)


def test_regra_inativa_nao_e_avaliada(db):
    regra = RegraAlerta(
        nome="Desativada", entidade="beneficiario", indicador="participacao_variacao",
        operador=">=", limite=0.0, severidade="critica", ativo=False,
    )
    db.add(regra)
    db.commit()
    resultado = alerts.avaliar_regras(db, date(2026, 6, 1), "mes_anterior")
    assert all(a.regra_id != regra.id for a in resultado)


def test_endpoint_alertas_avaliados(api):
    api.post(
        "/api/config/regras-alerta",
        json={"nome": "Prestador crescimento", "entidade": "prestador",
              "indicador": "crescimento_despesa", "operador": ">=", "limite": 20.0,
              "severidade": "atencao"},
    )
    r = api.get("/api/analytics/alertas?competencia=2026-06")
    assert r.status_code == 200
    b = r.json()
    assert b["total"] == len(b["itens"])
    if b["itens"]:
        item = b["itens"][0]
        campos = {"regra_nome", "entidade", "valor_observado", "limite", "severidade", "deep_link"}
        assert campos <= set(item)
