import uuid

import pytest
from fastapi.testclient import TestClient

from app import db
from app.auth import hash_password
from app.main import app


@pytest.fixture
def auth_client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")

    uid = uuid.uuid4().hex[:8]
    user_id = f"test_user_adv_{uid}"
    email = f"advanced_{uid}@exemplo.mz"
    with TestClient(app) as test_c:
        pwd_hash = hash_password("senha12345")
        db.create_user(user_id, email, pwd_hash, "Utilizador Avançado")
        test_c.post("/entrar", data={"email": email, "password": "senha12345"})
        yield test_c, user_id


def _create_manual_post(client, business: str):
    return client.post(
        "/posts",
        data={
            "business": business,
            "publish_as": "individual",
            "contact": "841234567",
        },
    )


def test_individual_post_uses_informal_category(auth_client):
    c, _ = auth_client
    resp = c.post(
        "/posts",
        data={
            "business": "Telemóvel Usado iPhone 11",
            "publish_as": "individual",
            "contact": "841234567",
            "price_mt": "15000",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"

    post = db.get_post(data["post_id"])
    assert post is not None
    assert post["category"] == "venda_informal"
    assert post["publisher_type"] == "individual"


def test_dislike_requires_reason(auth_client):
    c, _ = auth_client
    resp = _create_manual_post(c, "Item para teste dislike")
    post_id = resp.json()["post_id"]

    resp_dislike_fail = c.post(
        f"/posts/{post_id}/react",
        data={"reaction_type": "dislike", "reason": ""},
    )
    assert resp_dislike_fail.status_code == 422
    assert "obrigatório" in resp_dislike_fail.json()["error"]

    resp_dislike_ok = c.post(
        f"/posts/{post_id}/react",
        data={"reaction_type": "dislike", "reason": "Preço muito alto e sem fotos claras"},
    )
    assert resp_dislike_ok.status_code == 200
    assert resp_dislike_ok.json()["dislikes"] == 1

    reports = db.list_open_reports()
    dislike_reports = [
        r for r in reports
        if r["source"] == "dislike_feedback" and r["post_id"] == post_id
    ]
    assert len(dislike_reports) == 1
    assert "Preço muito alto" in dislike_reports[0]["reason"]


def test_comments_and_likes(auth_client):
    c, _ = auth_client
    resp = _create_manual_post(c, "Item para comentarios")
    post_id = resp.json()["post_id"]

    resp_like = c.post(f"/posts/{post_id}/react", data={"reaction_type": "like"})
    assert resp_like.status_code == 200
    assert resp_like.json()["likes"] == 1

    resp_comment = c.post(
        f"/posts/{post_id}/comments",
        data={"body": "Excelente oportunidade, aceitas troca?"},
    )
    assert resp_comment.status_code == 200
    assert resp_comment.json()["success"] is True

    comments = db.get_post_comments(post_id)
    assert len(comments) == 1
    assert comments[0]["body"] == "Excelente oportunidade, aceitas troca?"


def test_post_editing_and_deletion(auth_client):
    c, _ = auth_client
    resp = _create_manual_post(c, "Item para editar e apagar")
    post_id = resp.json()["post_id"]

    resp_edit = c.post(
        f"/posts/{post_id}/editar",
        data={
            "theme": "Item Editado Com Sucesso",
            "price_mt": "2500",
            "contact": "879998877",
            "location": "Maputo Central",
            "description": "Nova descrição editada pelo proprietário",
        },
        follow_redirects=False,
    )
    assert resp_edit.status_code == 303

    post_updated = db.get_post(post_id)
    assert post_updated["theme"] == "Item Editado Com Sucesso"
    assert post_updated["price_mt"] == 2500.0

    resp_del = c.post(f"/posts/{post_id}/eliminar", follow_redirects=False)
    assert resp_del.status_code == 303
    assert db.get_post(post_id) is None


def test_seasonal_theme_setting(auth_client):
    c, user_id = auth_client
    resp_theme = c.post(
        "/perfil/tema",
        data={"theme": "natal"},
        follow_redirects=False,
    )
    assert resp_theme.status_code == 303

    user_updated = db.get_user_by_id(user_id)
    assert user_updated["seasonal_theme"] == "natal"
