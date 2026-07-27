import pytest
from fastapi.testclient import TestClient

from app import db as db_module
from app.moderation import check_text_blocklist
from app.models import PostInput, PublisherType


def test_blocklist_detects_prohibited_term():
    matches = check_text_blocklist("Vendo pistola ilegal em bom estado")
    assert "pistola ilegal" in matches


def test_blocklist_clean_text_has_no_matches():
    matches = check_text_blocklist("Vendo camisa de algodão em bom estado")
    assert matches == []


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
        theme="Camisa vintage",
        business="Loja de roupa",
        category="moda_beleza",
        publisher_type=PublisherType.INDIVIDUAL,
        target_audience="Todos",
        objective="Vender",
        tone="amigável",
        call_to_action="Compra já",
        contact="871234567",
    )


def test_create_post_with_prohibited_content_rejected(client):
    _register(client, "vendedor@exemplo.co.mz", "Vendedor")
    resp = client.post(
        "/posts",
        data={
            "theme": "Venda de pistola ilegal usada",
            "business": "Armas",
            "category": "outro",
            "publisher_type": "individual",
            "target_audience": "Todos",
            "objective": "Vender",
            "tone": "neutro",
            "language": "pt",
            "call_to_action": "Compra já",
            "contact": "871234567",
        },
    )
    assert resp.status_code == 422
    assert "não permitido" in resp.json()["error"]


def test_report_hides_post_from_non_owner(client, monkeypatch):
    seller = _register(client, "vendedor2@exemplo.co.mz", "Vendedor2")
    db_module.create_post("post-mod-1", seller["user_id"], None, _dummy_post_input())
    db_module.update_status("post-mod-1", db_module.PostStatus.COMPLETED)
    client.post("/sair", follow_redirects=False)

    _register(client, "reporter@exemplo.co.mz", "Reporter")
    resp = client.post(
        "/posts/post-mod-1/reportar", data={"reason": "Produto suspeito"}, follow_redirects=False
    )
    assert resp.status_code == 303

    tx = db_module.get_post("post-mod-1")
    assert tx["moderation_status"] == "reported"

    view = client.get("/posts/post-mod-1")
    assert view.status_code == 404
    assert "post não encontrado" in view.text.lower()


def test_owner_can_still_see_own_reported_post(client):
    seller = _register(client, "vendedor3@exemplo.co.mz", "Vendedor3")
    db_module.create_post("post-mod-2", seller["user_id"], None, _dummy_post_input())
    db_module.update_status("post-mod-2", db_module.PostStatus.COMPLETED)
    db_module.set_post_moderation_status("post-mod-2", "reported")

    view = client.get("/posts/post-mod-2")
    assert view.status_code == 200
    assert "Camisa vintage" in view.text


def test_admin_can_resolve_report(client):
    seller = _register(client, "vendedor4@exemplo.co.mz", "Vendedor4")
    db_module.create_post("post-mod-3", seller["user_id"], None, _dummy_post_input())
    db_module.update_status("post-mod-3", db_module.PostStatus.COMPLETED)
    client.post("/sair", follow_redirects=False)

    reporter = _register(client, "reporter2@exemplo.co.mz", "Reporter2")
    client.post("/posts/post-mod-3/reportar", data={"reason": "Teste"}, follow_redirects=False)
    client.post("/sair", follow_redirects=False)

    non_admin = _register(client, "naoadmin@exemplo.co.mz", "NaoAdmin")
    resp = client.get("/admin/moderacao", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/explorar"

    with db_module.get_conn() as conn:
        conn.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (non_admin["user_id"],))

    resp = client.get("/admin/moderacao")
    assert resp.status_code == 200
    assert "Camisa vintage" in resp.text

    reports = db_module.list_open_reports()
    assert len(reports) == 1
    report_id = reports[0]["report_id"]

    resp = client.post(
        f"/admin/moderacao/{report_id}/resolver", data={"decision": "aprovar"}, follow_redirects=False
    )
    assert resp.status_code == 303
    assert db_module.get_post("post-mod-3")["moderation_status"] == "approved"
    assert db_module.list_open_reports() == []


def test_admin_email_bootstrap_grants_admin(client, monkeypatch):
    from app import config as config_module

    monkeypatch.setattr(config_module, "ADMIN_EMAIL", "chefe@exemplo.co.mz")
    user = _register(client, "chefe@exemplo.co.mz", "Chefe")
    assert user["is_admin"] == 1
