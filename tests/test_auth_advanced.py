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


def test_unverified_google_login_is_completely_disabled(client):
    get_resp = client.get(
        "/auth/google?google_id=google_user_123&email=maria.google@gmail.com&name=Maria+Google",
        follow_redirects=False,
    )
    post_resp = client.post(
        "/auth/google",
        data={
            "google_id": "google_user_123",
            "email": "maria.google@gmail.com",
            "name": "Maria Google",
        },
        follow_redirects=False,
    )

    assert get_resp.status_code == 404
    assert post_resp.status_code == 404
    assert db_module.get_user_by_email("maria.google@gmail.com") is None

    for path in ("/entrar", "/registar"):
        page = client.get(path)
        assert "/auth/google" not in page.text
        assert "com o Google" not in page.text
