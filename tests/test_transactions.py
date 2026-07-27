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


def _login(client, email):
    client.post("/entrar", data={"email": email, "password": "password123"}, follow_redirects=False)


def _dummy_post_input():
    return PostInput(
        theme="Bicicleta usada",
        business="Venda pessoal",
        category="outro",
        publisher_type=PublisherType.INDIVIDUAL,
        target_audience="Todos",
        objective="Vender",
        tone="neutro",
        call_to_action="Compra já",
        contact="871234567",
    )


def _create_public_post(post_id, user_id):
    db_module.create_post(post_id, user_id, None, _dummy_post_input())
    db_module.update_status(post_id, db_module.PostStatus.COMPLETED)


def _setup_transaction(client, with_mediation=False):
    seller = _register(client, "vendedor@exemplo.co.mz", "Vendedor")
    _create_public_post("post-tx-1", seller["user_id"])
    client.post("/sair", follow_redirects=False)

    buyer = _register(client, "comprador@exemplo.co.mz", "Comprador")
    resp = client.post(
        "/posts/post-tx-1/transacao",
        data={"with_mediation": "on"} if with_mediation else {},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    transaction_id = resp.headers["location"].rsplit("/", 1)[-1]
    return seller, buyer, transaction_id


def test_buyer_can_start_transaction(client):
    seller, buyer, transaction_id = _setup_transaction(client)
    tx = db_module.get_transaction(transaction_id)
    assert tx["status"] == "pendente"
    assert tx["buyer_id"] == buyer["user_id"]
    assert tx["seller_id"] == seller["user_id"]


def test_seller_cannot_start_transaction_on_own_post(client):
    seller = _register(client, "vendedor2@exemplo.co.mz", "Vendedor2")
    _create_public_post("post-tx-2", seller["user_id"])

    resp = client.post("/posts/post-tx-2/transacao", data={}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/posts/post-tx-2"
    assert db_module.list_transactions_for_user(seller["user_id"]) == []


def test_buyer_cannot_mark_vendido(client):
    seller, buyer, transaction_id = _setup_transaction(client)
    # buyer já está logado (foi o último a fazer login em _setup_transaction)
    resp = client.post(
        f"/transacoes/{transaction_id}/estado", data={"new_status": "vendido"}, follow_redirects=False
    )
    assert resp.status_code == 303
    tx = db_module.get_transaction(transaction_id)
    assert tx["status"] == "pendente"  # não mudou


def test_full_happy_path_pendente_vendido_recebido(client):
    seller, buyer, transaction_id = _setup_transaction(client)

    client.post("/sair", follow_redirects=False)
    _login(client, "vendedor@exemplo.co.mz")
    client.post(f"/transacoes/{transaction_id}/estado", data={"new_status": "vendido"}, follow_redirects=False)
    assert db_module.get_transaction(transaction_id)["status"] == "vendido"

    # vendedor não pode marcar recebido
    client.post(f"/transacoes/{transaction_id}/estado", data={"new_status": "recebido"}, follow_redirects=False)
    assert db_module.get_transaction(transaction_id)["status"] == "vendido"

    client.post("/sair", follow_redirects=False)
    _login(client, "comprador@exemplo.co.mz")
    resp = client.post(
        f"/transacoes/{transaction_id}/estado", data={"new_status": "recebido"}, follow_redirects=False
    )
    assert resp.status_code == 303
    assert db_module.get_transaction(transaction_id)["status"] == "recebido"


def test_recebido_is_terminal(client):
    seller, buyer, transaction_id = _setup_transaction(client)
    client.post("/sair", follow_redirects=False)
    _login(client, "vendedor@exemplo.co.mz")
    client.post(f"/transacoes/{transaction_id}/estado", data={"new_status": "vendido"}, follow_redirects=False)
    client.post("/sair", follow_redirects=False)
    _login(client, "comprador@exemplo.co.mz")
    client.post(f"/transacoes/{transaction_id}/estado", data={"new_status": "recebido"}, follow_redirects=False)

    client.post(f"/transacoes/{transaction_id}/estado", data={"new_status": "cancelado"}, follow_redirects=False)
    assert db_module.get_transaction(transaction_id)["status"] == "recebido"


def test_third_party_cannot_view_or_change_transaction(client):
    seller, buyer, transaction_id = _setup_transaction(client)
    client.post("/sair", follow_redirects=False)
    _register(client, "estranho@exemplo.co.mz", "Estranho")

    resp = client.get(f"/transacoes/{transaction_id}", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/transacoes"

    client.post(f"/transacoes/{transaction_id}/estado", data={"new_status": "vendido"}, follow_redirects=False)
    assert db_module.get_transaction(transaction_id)["status"] == "pendente"


def test_no_real_money_language_present_on_transaction_page(client):
    seller, buyer, transaction_id = _setup_transaction(client, with_mediation=True)
    resp = client.get(f"/transacoes/{transaction_id}")
    assert resp.status_code == 200
    assert "não processa nem retém dinheiro" in resp.text
