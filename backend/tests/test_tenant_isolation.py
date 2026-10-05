"""TESTE CRÍTICO — isolamento Tenant A × Tenant B (Fundação SaaS V1).

Cenário: dois tenants sintéticos com os MESMOS identificadores de negócio (BEN-000001…,
mesmos códigos de contrato/prestador/procedimento). Um MANAGER do Tenant A nunca pode
consultar, listar, agregar, pesquisar, inferir (por erro) ou alcançar por rota relacionada
qualquer dado do Tenant B.

Cada teste roda DUAS vezes (fixture `iso_mode`):
  * `runtime_rls`        — papel de runtime sem privilégio: aplicação + RLS;
  * `somente_aplicacao`  — papel dono (IGNORA RLS): prova que a aplicação isola sozinha.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from tests.conftest import TENANT_A, TENANT_B, iso_client

pytestmark = pytest.mark.scenarios


# ------------------------------------------------------------------------------ helpers
def _ids(iso_env, tabela: str, tenant: str, col: str = "id") -> set:
    with iso_env.owner() as s:
        return set(s.execute(text(f"SELECT {col} FROM {tabela} WHERE tenant_id = :t"),
                             {"t": tenant}).scalars())


def _ben(iso_env, tenant: str, codigo: str = "BEN-000001") -> int:
    with iso_env.owner() as s:
        return s.execute(text("SELECT id FROM beneficiarios WHERE tenant_id = :t AND codigo = :c"),
                         {"t": tenant, "c": codigo}).scalar_one()


def _algum(iso_env, tabela: str, tenant: str) -> int:
    with iso_env.owner() as s:
        return s.execute(text(f"SELECT min(id) FROM {tabela} WHERE tenant_id = :t"),
                         {"t": tenant}).scalar_one()


def _tem_dado_de_b(corpo: str, iso_env) -> bool:
    """Procura no corpo da resposta o nome de algum contrato exclusivo do tenant B."""
    with iso_env.owner() as s:
        nomes_b = set(s.execute(text("SELECT nome FROM contratos WHERE tenant_id = :b"), {"b": TENANT_B}).scalars())
        nomes_a = set(s.execute(text("SELECT nome FROM contratos WHERE tenant_id = :a"), {"a": TENANT_A}).scalars())
    return any(n in corpo for n in nomes_b - nomes_a)


# ================================================================== pré-condição do cenário
def test_cenario_tem_mesmo_identificador_nos_dois_tenants(iso_env):
    a, b = _ben(iso_env, TENANT_A), _ben(iso_env, TENANT_B)
    assert a != b  # mesmas chaves de negócio, linhas distintas
    with iso_env.owner() as s:
        codigos_ctr = s.execute(text(
            "SELECT count(*) FROM contratos a JOIN contratos b ON a.nome = b.nome "
            "WHERE a.tenant_id = :a AND b.tenant_id = :b"), {"a": TENANT_A, "b": TENANT_B}).scalar_one()
    assert codigos_ctr > 0, "esperava contratos com o mesmo nome nos dois tenants"


# ============================================================================ beneficiário
def test_detalhe_por_codigo_retorna_apenas_o_do_proprio_tenant(client_a, iso_env):
    r = client_a.get("/api/analytics/beneficiarios/BEN-000001")
    assert r.status_code == 200
    assert r.json()["beneficiario"]["id"] == _ben(iso_env, TENANT_A)


def test_detalhe_por_id_de_outro_tenant_e_404_sem_vazar(client_a, iso_env):
    id_b = _ben(iso_env, TENANT_B)
    for rota in (f"/api/analytics/beneficiarios/{id_b}", f"/api/analytics/beneficiarios/{id_b}/timeline"):
        r = client_a.get(rota)
        assert r.status_code == 404, rota
        assert "BEN-" not in r.text and str(id_b) not in r.json()["detail"]


def test_listagem_e_busca_de_beneficiarios_so_trazem_o_proprio_tenant(client_a, iso_env):
    ids_a = _ids(iso_env, "beneficiarios", TENANT_A)
    for params in ("", "&sexo=F", "&faixa_etaria=60-69", "&page_size=200"):
        r = client_a.get(f"/api/analytics/beneficiarios?competencia=2026-06{params}")
        assert r.status_code == 200
        itens = r.json()["itens"]
        assert itens and {i["id"] for i in itens} <= ids_a


def test_eventos_do_beneficiario_sao_do_proprio_tenant(client_a, iso_env):
    r = client_a.get("/api/analytics/beneficiarios/BEN-000001")
    eventos_a = _ids(iso_env, "eventos_assistenciais", TENANT_A)
    ids = {e["id"] for e in r.json().get("eventos", [])}
    assert ids <= eventos_a


# =============================================================================== contrato
def test_contratos_lista_e_detalhe(client_a, iso_env):
    ids_a = _ids(iso_env, "contratos", TENANT_A)
    r = client_a.get("/api/analytics/contratos?competencia=2026-08")
    assert r.status_code == 200
    assert {c["id_contrato"] for c in r.json()["itens"]} <= ids_a
    id_b = _algum(iso_env, "contratos", TENANT_B)
    assert client_a.get(f"/api/analytics/contratos/{id_b}?competencia=2026-08").status_code == 404


def test_contrato_de_outro_tenant_como_escopo_e_filtro_e_404(client_a, iso_env):
    id_b = _algum(iso_env, "contratos", TENANT_B)
    for rota in (
        f"/api/analytics/sinistralidade/explain?competencia=2026-08&contrato_id={id_b}",
        f"/api/analytics/sinistralidade/composicao?competencia=2026-08&contrato_id={id_b}",
        f"/api/analytics/beneficiarios?competencia=2026-08&contrato_id={id_b}",  # a rota lê `contrato_id`
    ):
        assert client_a.get(rota).status_code == 404, rota


# ============================================================================== prestador
def test_prestadores_lista_ranking_anomalias_e_detalhe(client_a, iso_env):
    ids_a = _ids(iso_env, "prestadores", TENANT_A)
    r = client_a.get("/api/analytics/prestadores?competencia=2026-06&page_size=200")
    assert r.status_code == 200 and {p["id_prestador"] for p in r.json()["itens"]} <= ids_a
    r = client_a.get("/api/analytics/prestadores/ranking-variacao?competencia=2026-06")
    assert {p["id_prestador"] for p in r.json()["itens"]} <= ids_a
    r = client_a.get("/api/analytics/prestadores/anomalias?competencia=2026-06")
    assert {p["id_prestador"] for p in r.json()["itens"]} <= ids_a
    id_b = _algum(iso_env, "prestadores", TENANT_B)
    assert client_a.get(f"/api/analytics/prestadores/{id_b}?competencia=2026-06").status_code == 404


# ======================================================================= procedimento/drill
def test_procedimento_de_outro_tenant_nao_retorna_dado(client_a, iso_env):
    id_b = _algum(iso_env, "procedimentos", TENANT_B)
    r = client_a.get(f"/api/analytics/procedimentos/{id_b}?competencia=2026-06")
    assert r.status_code == 404
    r = client_a.get(f"/api/analytics/sinistralidade/explain/procedimento/{id_b}?competencia=2026-06")
    assert r.status_code == 404


# ============================================================================== agregação
def test_agregacoes_batem_com_o_tenant_a_e_nao_com_o_b(client_a, iso_env):
    with iso_env.owner() as s:
        q = text("SELECT despesa_liquida, receita FROM agg_sinistralidade_competencia "
                 "WHERE tenant_id = :t AND competencia = '2026-06-01'")
        a = s.execute(q, {"t": TENANT_A}).mappings().one()
        b = s.execute(q, {"t": TENANT_B}).mappings().one()
    r = client_a.get("/api/executive/overview?competencia=2026-06")
    assert r.status_code == 200
    k = r.json()["kpis"]
    assert k["despesa"] == pytest.approx(float(a["despesa_liquida"]), abs=0.01)
    assert k["receita"] == pytest.approx(float(a["receita"]), abs=0.01)
    assert k["despesa"] != pytest.approx(float(b["despesa_liquida"]), abs=0.01)
    serie = client_a.get("/api/analytics/sinistralidade/evolucao").json()["serie"]
    assert len(serie) == 24  # uma linha por competência — sem somar o outro tenant


def test_catalogos_e_competencias_so_do_proprio_tenant(client_a, iso_env):
    for nome, tabela in (("planos", "planos"), ("contratos", "contratos"),
                         ("regioes", "regioes"), ("especialidades", "especialidades")):
        r = client_a.get(f"/api/catalogos/{nome}")
        assert r.status_code == 200
        assert {i["id"] for i in r.json()["itens"]} == _ids(iso_env, tabela, TENANT_A), nome


def test_explicacao_e_drill_nao_trazem_entidades_de_b(client_a, iso_env):
    prest_a = _ids(iso_env, "prestadores", TENANT_A)
    ben_a = _ids(iso_env, "beneficiarios", TENANT_A)
    r = client_a.get("/api/analytics/sinistralidade/explain?competencia=2026-06&dimensao=prestador")
    assert r.status_code == 200
    for f in r.json()["principais_fatores"] + r.json()["fatores_reducao"]:
        assert int(f["chave"]) in prest_a
    chave = r.json()["principais_fatores"][0]["chave"]
    d = client_a.get(f"/api/analytics/sinistralidade/explain/prestador/{chave}?competencia=2026-06").json()
    for b in d["onde_investigar"]["beneficiarios_maior_despesa"]:
        assert b["id"] in ben_a
    assert not _tem_dado_de_b(r.text + str(d), iso_env)


# =============================================================================== insights
def test_insights_e_deep_links_so_do_proprio_tenant(client_a, iso_env):
    prest_a = _ids(iso_env, "prestadores", TENANT_A)
    ben_a = _ids(iso_env, "beneficiarios", TENANT_A)
    for comp in ("2026-06", "2026-07", "2026-09"):
        r = client_a.get(f"/api/analytics/insights?competencia={comp}&limit=100")
        assert r.status_code == 200
        for i in r.json()["itens"]:
            rota = i["deep_link"]["rota"]
            if rota.startswith("/prestadores/"):
                assert int(rota.rsplit("/", 1)[1]) in prest_a
            if rota.startswith("/beneficiarios/"):
                assert int(rota.rsplit("/", 1)[1]) in ben_a
        assert not _tem_dado_de_b(r.text, iso_env)


def test_gabarito_e_do_proprio_tenant(client_a, iso_env):
    r = client_a.get("/api/analytics/gabarito")
    assert r.status_code == 200
    with iso_env.owner() as s:
        chaves_a = set(s.execute(text("SELECT chave_alvo FROM cenarios_gabarito WHERE tenant_id = :t"),
                                 {"t": TENANT_A}).scalars())
    assert {g["chave_alvo"] for g in r.json()["itens"]} == chaves_a


# ================================================================================ alertas
def test_regras_e_alertas_isolados_e_idor_bloqueado(client_a, iso_env):
    regras_a = _ids(iso_env, "regras_alerta", TENANT_A)
    r = client_a.get("/api/config/regras-alerta")
    assert r.status_code == 200 and {x["id"] for x in r.json()} == regras_a
    id_b = _algum(iso_env, "regras_alerta", TENANT_B)
    assert client_a.get(f"/api/config/regras-alerta/{id_b}").status_code == 404
    assert client_a.put(f"/api/config/regras-alerta/{id_b}", json={"limite": 1.0}).status_code == 404
    assert client_a.delete(f"/api/config/regras-alerta/{id_b}").status_code == 404
    with iso_env.owner() as s:  # a regra de B continua intacta
        lim = s.execute(text("SELECT limite FROM regras_alerta WHERE id = :i"), {"i": id_b}).scalar_one()
    assert lim != 1.0
    r = client_a.get("/api/analytics/alertas?competencia=2026-08")
    assert r.status_code == 200
    for a in r.json()["itens"]:
        assert a["regra_id"] in regras_a


# ===================================================== tenant arbitrário não altera contexto
def test_tenant_id_enviado_pelo_cliente_e_ignorado(client_a, iso_env):
    esperado = client_a.get("/api/executive/overview?competencia=2026-06").json()["kpis"]
    for kwargs in ({"params": {"tenant_id": TENANT_B, "competencia": "2026-06"}},
                   {"params": {"competencia": "2026-06"}, "headers": {"X-Tenant-ID": TENANT_B}},
                   {"params": {"competencia": "2026-06"}, "cookies": {"tenant": TENANT_B}}):
        r = client_a.get("/api/executive/overview", **kwargs)
        assert r.status_code == 200 and r.json()["kpis"] == esperado


def test_tenant_id_no_corpo_nao_cria_regra_em_outro_tenant(client_a, iso_env):
    payload = {"nome": "Tentativa cruzada", "entidade": "prestador", "indicador": "crescimento_despesa",
               "operador": ">=", "limite": 99.0, "severidade": "atencao", "tenant_id": TENANT_B}
    r = client_a.post("/api/config/regras-alerta", json=payload)
    assert r.status_code == 201
    with iso_env.owner() as s:
        tid = s.execute(text("SELECT tenant_id FROM regras_alerta WHERE id = :i"), {"i": r.json()["id"]}).scalar_one()
        s.execute(text("DELETE FROM regras_alerta WHERE id = :i"), {"i": r.json()["id"]})
        s.commit()
    assert tid == TENANT_A


def test_troca_para_tenant_sem_vinculo_e_negada(client_a):
    r = client_a.post("/api/auth/switch-tenant", json={"tenant_id": TENANT_B})
    assert r.status_code == 403 and r.json()["code"] == "forbidden"


def test_token_com_tenant_divergente_da_sessao_e_rejeitado(iso_env):
    """Mesmo com a chave correta, um access token cujo `tid` não confere com a sessão
    (tentativa de forjar contexto) é recusado."""
    from sqlalchemy import select

    from app.models import AuthSession, User
    from app.security.tokens import create_access_token
    from tests.conftest import make_client, token_for

    with iso_env.owner() as s:
        token_for(s, "a.manager@iso.example", TENANT_A)
        u = s.execute(select(User).where(User.email == "a.manager@iso.example")).scalar_one()
        sess = s.execute(select(AuthSession).where(AuthSession.user_id == u.id)
                         .order_by(AuthSession.created_at.desc())).scalars().first()
        forjado, _ = create_access_token(user_id=u.id, session_id=sess.id, tenant_id=TENANT_B,
                                         token_version=u.token_version)
    c = make_client(iso_env.app, {"Authorization": f"Bearer {forjado}"})
    assert c.get("/api/executive/overview").status_code == 401


def test_usuario_b_ve_o_seu_beneficiario_000001(iso_env):
    c = iso_client(iso_env, "b.manager@iso.example", TENANT_B)
    r = c.get("/api/analytics/beneficiarios/BEN-000001")
    assert r.status_code == 200 and r.json()["beneficiario"]["id"] == _ben(iso_env, TENANT_B)
