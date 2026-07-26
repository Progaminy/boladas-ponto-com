import pytest
from fastapi.testclient import TestClient

from app import auth
from app import db as db_module


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_hash_password_roundtrip():
    hashed = auth.hash_password("segredo-forte-123")
    assert hashed != "segredo-forte-123"
    assert auth.verify_password("segredo-forte-123", hashed)
    assert not auth.verify_password("errada", hashed)


def test_register_logs_in_and_redirects_to_explorar(client):
    resp = client.post(
        "/registar",
        data={"email": "ana@exemplo.co.mz", "password": "password123", "display_name": "Ana", "terms_accepted": "on"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/explorar"

    follow = client.get("/explorar")
    assert follow.status_code == 200
    assert "Feed" in follow.text


def test_register_without_accepting_terms_rejected(client):
    resp = client.post(
        "/registar",
        data={"email": "semtermos@exemplo.co.mz", "password": "password123", "display_name": "Sem Termos"},
        follow_redirects=False,
    )
    assert resp.status_code == 422
    assert db_module.get_user_by_email("semtermos@exemplo.co.mz") is None


def test_terms_page_accessible_without_session(client):
    resp = client.get("/termos")
    assert resp.status_code == 200
    assert "Termos de Uso" in resp.text


def test_register_duplicate_email_rejected(client):
    payload = {"email": "dup@exemplo.co.mz", "password": "password123", "display_name": "Dup", "terms_accepted": "on"}
    client.post("/registar", data=payload, follow_redirects=False)
    resp = client.post("/registar", data=payload, follow_redirects=False)
    assert resp.status_code == 409
    assert "Já existe" in resp.text


def test_login_wrong_password_rejected(client):
    client.post(
        "/registar",
        data={"email": "bob@exemplo.co.mz", "password": "password123", "display_name": "Bob", "terms_accepted": "on"},
        follow_redirects=False,
    )
    client.post("/sair", follow_redirects=False)

    resp = client.post(
        "/entrar", data={"email": "bob@exemplo.co.mz", "password": "errada"}, follow_redirects=False
    )
    assert resp.status_code == 401


def test_protected_routes_redirect_when_logged_out(client):
    for path in ["/criar", "/historico", "/empresa"]:
        resp = client.get(path, follow_redirects=False)
        assert resp.status_code == 303, path
        assert resp.headers["location"] == "/entrar", path


def test_explorar_public_without_session(client):
    resp = client.get("/explorar", follow_redirects=False)
    assert resp.status_code == 200


def test_create_post_without_session_returns_401(client):
    valid_payload = {
        "theme": "Promoção",
        "business": "Loja X",
        "category": "outro",
        "publisher_type": "individual",
        "target_audience": "Todos",
        "objective": "Vender",
        "tone": "amigável",
        "language": "pt",
        "call_to_action": "Compra já",
        "contact": "871234567",
    }
    resp = client.post("/posts", data=valid_payload)
    assert resp.status_code == 401
    assert resp.json()["error"]


def test_post_result_and_provenance_public_without_session(client):
    # partilhável sem conta — devolve 404 real (não redireciona para /entrar)
    # porque o post não existe, mas a rota em si não exige sessão.
    resp = client.get("/posts/inexistente", follow_redirects=False)
    assert resp.status_code == 404

    resp = client.get("/posts/inexistente/provenance", follow_redirects=False)
    assert resp.status_code == 404


def test_explorar_accessible_for_logged_in_user(client):
    resp = client.post(
        "/registar",
        data={"email": "exp@exemplo.co.mz", "password": "password123", "display_name": "Exp", "terms_accepted": "on"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    resp = client.get("/explorar")
    assert resp.status_code == 200


def test_landing_page_shown_when_logged_out(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 200
    assert "Feed" in resp.text
