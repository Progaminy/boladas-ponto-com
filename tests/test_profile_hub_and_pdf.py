"""Testes para o Hub de Gestão do Perfil e Faturas Eletrónicas PDF.
"""

import pytest
from fastapi.testclient import TestClient
from app import db as db_module


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_profile_redirect_and_tab_navigation(client):
    # 1. Autenticar utilizador
    client.post(
        "/registar",
        data={
            "auth_method": "email",
            "email": "gestor@exemplo.co.mz",
            "password": "segredo-forte-123",
            "display_name": "Gestor de Loja",
            "terms_accepted": "on",
        },
    )

    # 2. Aceder a /perfil redireciona para /utilizador/{user_id}?tab=produtos
    resp = client.get("/perfil", follow_redirects=False)
    assert resp.status_code == 303
    assert "/utilizador/" in resp.headers["location"]
    assert "tab=produtos" in resp.headers["location"]

    # 3. Navegar nas abas do perfil hub
    user_url = resp.headers["location"]
    res_produtos = client.get(user_url)
    assert res_produtos.status_code == 200
    assert "Os Meus Produtos" in res_produtos.text

    res_empresas = client.get(user_url.replace("tab=produtos", "tab=empresas"))
    assert res_empresas.status_code == 200
    assert "As Minhas Empresas Registadas" in res_empresas.text

    res_faturas = client.get(user_url.replace("tab=produtos", "tab=faturas"))
    assert res_faturas.status_code == 200
    assert "Faturas Eletrónicas" in res_faturas.text


def test_post_status_change_and_pdf_invoice(client):
    # 1. Registo e criar post
    client.post(
        "/registar",
        data={
            "auth_method": "email",
            "email": "vendedor@exemplo.co.mz",
            "password": "segredo-forte-123",
            "display_name": "Vendedor Moz",
            "terms_accepted": "on",
        },
    )

    post_resp = client.post(
        "/posts",
        data={
            "theme": "Gerador Inverter 5kW Diesel",
            "business": "Ferragem Central",
            "category": "ferragens",
            "publish_as": "individual",
            "price_mt": "45000",
            "currency": "MZN",
            "contact": "841234567",
            "location": "Maputo",
            "description": "Gerador novo na caixa com garantia",
        },
    )
    assert post_resp.status_code in (200, 502)
    post_id = post_resp.json()["post_id"]

    # 2. Alternar estado do produto (ativo -> pendente -> vendido)
    st_resp = client.post(
        f"/posts/{post_id}/estado",
        data={"new_status": "pendente"},
        follow_redirects=False,
    )
    assert st_resp.status_code == 303

    post_data = db_module.get_post(post_id)
    assert post_data["status"] == "pendente"

    st_resp2 = client.post(
        f"/posts/{post_id}/estado",
        data={"new_status": "vendido"},
        follow_redirects=False,
    )
    assert st_resp2.status_code == 303

    post_data2 = db_module.get_post(post_id)
    assert post_data2["status"] == "vendido"

    # 3. Gerar e descarregar Fatura Eletrónica PDF
    pdf_resp = client.get(f"/posts/{post_id}/fatura.pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert len(pdf_resp.content) > 1000
    assert b"%PDF" in pdf_resp.content[:10]
