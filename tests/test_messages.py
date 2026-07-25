import pytest
from fastapi.testclient import TestClient

from app import db as db_module
from app.models import PostInput, PublisherType


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    from app.main import app

    with TestClient(app) as c:
        yield c


def _register(client, email, name="Nome"):
    client.post(
        "/registar",
        data={"email": email, "password": "password123", "display_name": name, "terms_accepted": "on"},
        follow_redirects=False,
    )
    return db_module.get_user_by_email(email)


def _dummy_post_input():
    return PostInput(
        theme="Sapato de couro",
        business="Loja de sapatos",
        category="moda_beleza",
        publisher_type=PublisherType.INDIVIDUAL,
        target_audience="Todos",
        objective="Vender",
        tone="amigável",
        call_to_action="Compra já",
        contact="871234567",
    )


def test_contact_post_owner_creates_message_and_thread(client):
    seller = _register(client, "vendedor@exemplo.co.mz", "Vendedor")
    db_module.create_post("post-1", seller["user_id"], None, _dummy_post_input())
    client.post("/sair", follow_redirects=False)

    buyer = _register(client, "comprador@exemplo.co.mz", "Comprador")

    resp = client.post(
        "/posts/post-1/contactar", data={"body": "Ainda tens este sapato?"}, follow_redirects=False
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/mensagens/posto/post-1/{seller['user_id']}"

    thread = client.get(f"/mensagens/posto/post-1/{seller['user_id']}")
    assert thread.status_code == 200
    assert "Ainda tens este sapato?" in thread.text
    assert "post-1" in thread.text  # referência ao produto incluída na 1ª mensagem


def test_owner_can_reply_to_buyer(client):
    seller = _register(client, "vendedor2@exemplo.co.mz", "Vendedor2")
    db_module.create_post("post-2", seller["user_id"], None, _dummy_post_input())
    client.post("/sair", follow_redirects=False)

    buyer = _register(client, "comprador2@exemplo.co.mz", "Comprador2")
    client.post("/posts/post-2/contactar", data={"body": "Disponível?"}, follow_redirects=False)
    client.post("/sair", follow_redirects=False)

    client.post(
        "/entrar", data={"email": "vendedor2@exemplo.co.mz", "password": "password123"},
        follow_redirects=False,
    )

    resp = client.post(
        f"/mensagens/posto/post-2/{buyer['user_id']}",
        data={"body": "Sim, ainda tenho!"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    thread = client.get(f"/mensagens/posto/post-2/{buyer['user_id']}")
    assert "Sim, ainda tenho!" in thread.text


def test_cannot_contact_own_post(client):
    seller = _register(client, "vendedor3@exemplo.co.mz", "Vendedor3")
    db_module.create_post("post-3", seller["user_id"], None, _dummy_post_input())

    resp = client.post(
        "/posts/post-3/contactar", data={"body": "Teste"}, follow_redirects=False
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/posts/post-3"

    messages = db_module.list_messages_for_user(seller["user_id"])
    assert messages == []


def test_platform_contact_thread(client):
    user = _register(client, "ajuda@exemplo.co.mz", "PedeAjuda")

    resp = client.post(
        "/mensagens/plataforma", data={"body": "Preciso de ajuda com uma compra"}, follow_redirects=False
    )
    assert resp.status_code == 303

    thread = client.get("/mensagens/plataforma")
    assert "Preciso de ajuda com uma compra" in thread.text


def test_inbox_lists_conversations(client):
    seller = _register(client, "vendedor4@exemplo.co.mz", "Vendedor4")
    db_module.create_post("post-4", seller["user_id"], None, _dummy_post_input())
    client.post("/sair", follow_redirects=False)

    _register(client, "comprador4@exemplo.co.mz", "Comprador4")
    client.post("/posts/post-4/contactar", data={"body": "Olá"}, follow_redirects=False)

    resp = client.get("/mensagens")
    assert resp.status_code == 200
    assert "Vendedor4" in resp.text
