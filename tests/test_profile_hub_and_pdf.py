"""Testes para o Hub de Gestão do Perfil e Faturas Eletrónicas PDF."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app import db as db_module
from app.models import ListingStatus, PostInput, PostStatus, PublisherType


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
    # 1. Registar o vendedor e criar um post concluído sem depender de IA/B2.
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

    seller = db_module.get_user_by_email("vendedor@exemplo.co.mz")
    post_id = f"post-listing-{uuid.uuid4().hex}"
    post_input = PostInput(
        theme="Gerador Inverter 5kW Diesel",
        business="Ferragem Central",
        category="ferragens",
        publisher_type=PublisherType.INDIVIDUAL,
        target_audience="Clientes em Maputo",
        objective="Vender",
        tone="direto",
        call_to_action="Contacta-me",
        price_mt=45000,
        currency="MZN",
        contact="841234567",
        location="Maputo",
        description="Gerador novo na caixa com garantia",
    )
    db_module.create_post(post_id, seller["user_id"], None, post_input)
    db_module.update_status(post_id, PostStatus.COMPLETED)

    original = db_module.get_post(post_id)
    assert original["status"] == "completed"
    assert original["listing_status"] == "active"

    # 2. A disponibilidade muda sem corromper o estado técnico do pipeline.
    st_resp = client.post(
        f"/posts/{post_id}/estado",
        data={"new_status": "paused"},
        follow_redirects=False,
    )
    assert st_resp.status_code == 303

    post_data = db_module.get_post(post_id)
    assert post_data["status"] == "completed"
    assert post_data["listing_status"] == "paused"
    assert all(
        row["post_id"] != post_id
        for row in db_module.list_public_individual_posts_by_user(
            seller["user_id"]
        )
    )

    st_resp2 = client.post(
        f"/posts/{post_id}/estado",
        data={"new_status": "sold"},
        follow_redirects=False,
    )
    assert st_resp2.status_code == 303

    post_data2 = db_module.get_post(post_id)
    assert post_data2["status"] == "completed"
    assert post_data2["listing_status"] == "sold"

    invalid_resp = client.post(
        f"/posts/{post_id}/estado",
        data={"new_status": "vendido"},
        follow_redirects=False,
    )
    assert invalid_resp.status_code == 422
    assert db_module.get_post(post_id)["listing_status"] == "sold"

    # 3. Gerar e descarregar Fatura Eletrónica PDF
    pdf_resp = client.get(f"/posts/{post_id}/fatura.pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert len(pdf_resp.content) > 1000
    assert b"%PDF" in pdf_resp.content[:10]


def test_listing_status_requires_completed_post(client):
    client.post(
        "/registar",
        data={
            "auth_method": "email",
            "email": "pipeline@exemplo.co.mz",
            "password": "segredo-forte-123",
            "display_name": "Pipeline",
            "terms_accepted": "on",
        },
    )
    user = db_module.get_user_by_email("pipeline@exemplo.co.mz")
    post_id = f"post-pending-{uuid.uuid4().hex}"
    db_module.create_post(
        post_id,
        user["user_id"],
        None,
        PostInput(
            theme="Produto ainda em processamento",
            business="Produto em processamento",
            publisher_type=PublisherType.INDIVIDUAL,
            target_audience="Clientes",
            objective="Vender",
            tone="direto",
            call_to_action="Aguarda",
            contact="841234567",
        ),
    )

    response = client.post(
        f"/posts/{post_id}/estado",
        data={"new_status": "paused"},
        follow_redirects=False,
    )
    assert response.status_code == 409
    row = db_module.get_post(post_id)
    assert row["status"] == "pending"
    assert row["listing_status"] == "active"

    with pytest.raises(ValueError, match="depois de o post estar concluído"):
        db_module.update_listing_status(post_id, ListingStatus.SOLD)


@pytest.mark.parametrize(
    ("legacy_status", "expected_listing_status"),
    [
        ("ativo", "active"),
        ("pendente", "paused"),
        ("vendido", "sold"),
    ],
)
def test_legacy_commercial_status_migration(
    client, legacy_status, expected_listing_status
):
    user = db_module.get_user_by_email("carlos.ferragem@boladas.co.mz")
    post_id = f"legacy-{legacy_status}-{uuid.uuid4().hex}"
    db_module.create_post(
        post_id,
        user["user_id"],
        None,
        PostInput(
            theme=f"Produto legado {legacy_status}",
            business="Loja Legada",
            publisher_type=PublisherType.INDIVIDUAL,
            target_audience="Clientes",
            objective="Vender",
            tone="direto",
            call_to_action="Contacta-nos",
            contact="841234567",
        ),
    )
    db_module.update_status(post_id, legacy_status)

    db_module.init_db()

    migrated = db_module.get_post(post_id)
    assert migrated["status"] == "completed"
    assert migrated["listing_status"] == expected_listing_status
