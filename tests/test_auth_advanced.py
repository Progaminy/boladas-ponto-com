import pytest
from fastapi.testclient import TestClient

from app import db as db_module


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    from app.main import app

    with TestClient(app) as c:
        yield c

def test_register_and_login_by_phone(client):
    # 1. Registo por Número de Telefone + Prefixo (+258)
    resp = client.post(
        "/registar",
        data={
            "auth_method": "phone",
            "phone_prefix": "+258",
            "phone": "849998877",
            "password": "segredo-forte-123",
            "display_name": "Carlos Moz",
            "terms_accepted": "on",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/explorar"

    # Sair
    client.post("/sair")

    # 2. Login usando o Número de Telefone (+258 849998877)
    login_resp = client.post(
        "/entrar",
        data={
            "identifier": "+258 849998877",
            "password": "segredo-forte-123",
        },
        follow_redirects=False,
    )
    assert login_resp.status_code == 303
    assert login_resp.headers["location"] == "/explorar"


def test_google_sign_in_flow(client):
    # Registo/Login rápido por Conta Google
    resp = client.get(
        "/auth/google?google_id=google_user_123&email=maria.google@gmail.com&name=Maria+Google",
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/explorar"

    # Verificar se a sessão foi iniciada
    feed = client.get("/explorar")
    assert feed.status_code == 200
    assert "Maria Google" in feed.text
