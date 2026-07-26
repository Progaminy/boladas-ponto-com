import uuid
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import db
from app.main import app
from app.auth import hash_password
from app.pipeline import CaptionResult
from app.storage import UploadedFile

client = TestClient(app)


def _fake_caption(*args, **kwargs):
    return CaptionResult(
        caption="Texto de teste.",
        call_to_action="Contacta-me!",
        hashtags=["teste"],
        provider="test-provider",
        model="test-model",
    )


def _fake_upload(key, data, content_type):
    return UploadedFile(
        key=key,
        content_type=content_type,
        size=len(data),
        sha256="1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        url=f"https://fake-b2.example/{key}",
    )


@pytest.fixture
def auth_client():
    uid = uuid.uuid4().hex[:8]
    user_id = f"test_user_adv_{uid}"
    email = f"advanced_{uid}@exemplo.mz"
    pwd_hash = hash_password("senha12345")
    db.create_user(user_id, email, pwd_hash, "Utilizador Avançado")

    test_c = TestClient(app)
    test_c.post("/entrar", data={"email": email, "password": "senha12345"})
    return test_c, user_id


@patch("app.routers.posts.generate_caption", side_effect=_fake_caption)
@patch("app.routers.posts.upload_and_verify", side_effect=_fake_upload)
def test_individual_post_category_auto(mock_upload, mock_caption, auth_client):
    c, user_id = auth_client
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
    post_id = data["post_id"]

    post = db.get_post(post_id)
    assert post is not None
    assert post["category"] == "venda_informal"
    assert post["publisher_type"] == "individual"


@patch("app.routers.posts.generate_caption", side_effect=_fake_caption)
@patch("app.routers.posts.upload_and_verify", side_effect=_fake_upload)
def test_dislike_requires_reason(mock_upload, mock_caption, auth_client):
    c, user_id = auth_client
    resp = c.post(
        "/posts",
        data={
            "business": "Item para teste dislike",
            "publish_as": "individual",
            "contact": "841234567",
        },
    )
    post_id = resp.json()["post_id"]

    # tentar dislike sem motivo -> 422 Error
    resp_dislike_fail = c.post(
        f"/posts/{post_id}/react",
        data={"reaction_type": "dislike", "reason": ""},
    )
    assert resp_dislike_fail.status_code == 422
    assert "obrigatório" in resp_dislike_fail.json()["error"]

    # dislike com motivo -> sucesso + report automático gerado
    resp_dislike_ok = c.post(
        f"/posts/{post_id}/react",
        data={"reaction_type": "dislike", "reason": "Preço muito alto e sem fotos claras"},
    )
    assert resp_dislike_ok.status_code == 200
    res_data = resp_dislike_ok.json()
    assert res_data["dislikes"] == 1

    # Verificar que foi gerado um alerta de moderação para a equipa da plataforma
    reports = db.list_open_reports()
    dislike_reports = [r for r in reports if r["source"] == "dislike_feedback" and r["post_id"] == post_id]
    assert len(dislike_reports) == 1
    assert "Preço muito alto" in dislike_reports[0]["reason"]


@patch("app.routers.posts.generate_caption", side_effect=_fake_caption)
@patch("app.routers.posts.upload_and_verify", side_effect=_fake_upload)
def test_comments_and_likes(mock_upload, mock_caption, auth_client):
    c, user_id = auth_client
    resp = c.post(
        "/posts",
        data={
            "business": "Item para comentarios",
            "publish_as": "individual",
            "contact": "841234567",
        },
    )
    post_id = resp.json()["post_id"]

    # Like
    resp_like = c.post(f"/posts/{post_id}/react", data={"reaction_type": "like"})
    assert resp_like.status_code == 200
    assert resp_like.json()["likes"] == 1

    # Comentário
    resp_comment = c.post(
        f"/posts/{post_id}/comments",
        data={"body": "Excelente oportunidade, aceitas troca?"},
    )
    assert resp_comment.status_code == 200
    assert resp_comment.json()["success"] is True

    comments = db.get_post_comments(post_id)
    assert len(comments) == 1
    assert comments[0]["body"] == "Excelente oportunidade, aceitas troca?"


@patch("app.routers.posts.generate_caption", side_effect=_fake_caption)
@patch("app.routers.posts.upload_and_verify", side_effect=_fake_upload)
def test_post_editing_and_deletion(mock_upload, mock_caption, auth_client):
    c, user_id = auth_client
    resp = c.post(
        "/posts",
        data={
            "business": "Item para editar e apagar",
            "publish_as": "individual",
            "contact": "841234567",
        },
    )
    post_id = resp.json()["post_id"]

    # Editar
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

    # Eliminar
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
