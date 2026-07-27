import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import db
from app.auth import hash_password
from app.main import app
from app.models import PostInput, PublisherType
from app.storage import UploadedFile

def _fake_upload(key, data, content_type):
    return UploadedFile(
        key=key,
        content_type=content_type,
        size=len(data),
        sha256="1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        url=f"https://fake-b2.example/{key}",
    )


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    with TestClient(app) as test_client:
        yield test_client


@patch("app.routers.posts.upload_and_verify", side_effect=_fake_upload)
def test_full_interface_flow_reactions_and_comments(mock_upload, client):
    uid = uuid.uuid4().hex[:8]
    email = f"react_user_{uid}@exemplo.mz"
    user_id = f"user_react_{uid}"
    db.create_user(user_id, email, hash_password("senha12345"), "Utilizador Reação Teste")

    client.post("/entrar", data={"email": email, "password": "senha12345"})

    # 1. Criar post de teste
    post_id = uuid.uuid4().hex
    post_input = PostInput(
        theme="Cadeira de Escritório Ergonómica",
        business="Cadeira de Escritório Ergonómica",
        category="venda_informal",
        publisher_type=PublisherType.INDIVIDUAL,
        brand_name=None,
        target_audience="Todos",
        objective="Vender",
        tone="casual",
        language="pt",
        call_to_action="Contacta-me já!",
        price_mt=4500.0,
        location="Maputo",
        contact="849998877",
        description="Nova em caixa",
    )
    db.create_post(post_id, user_id, None, post_input)
    db.update_status(post_id, db.PostStatus.COMPLETED)

    # 2. Testar reações por formulário HTML (type="like" + referer) -> DEVE responder 303 Redirect sem erro 422!
    resp_like = client.post(
        f"/posts/{post_id}/react",
        data={"type": "like"},
        headers={"referer": "http://testserver/explorar"},
        follow_redirects=False,
    )
    assert resp_like.status_code == 303, f"Falhou com status {resp_like.status_code}: {resp_like.text}"

    # 3. Testar dislike por formulário HTML (type="dislike", reason="Motivo claro") -> DEVE responder 303!
    resp_dislike = client.post(
        f"/posts/{post_id}/react",
        data={"type": "dislike", "reason": "Preço muito elevado para o estado real"},
        headers={"referer": "http://testserver/explorar"},
        follow_redirects=False,
    )
    assert resp_dislike.status_code == 303

    # 4. Testar comentário por formulário HTML -> DEVE responder 303!
    resp_comment = client.post(
        f"/posts/{post_id}/comments",
        data={"body": "Ainda está disponível em Maputo?"},
        headers={"referer": "http://testserver/explorar"},
        follow_redirects=False,
    )
    assert resp_comment.status_code == 303
    assert resp_comment.headers["location"] == f"/posts/{post_id}"

    # 5. Confirmar que o comentário foi gravado
    comments = db.get_post_comments(post_id)
    assert len(comments) == 1
    assert comments[0]["body"] == "Ainda está disponível em Maputo?"


def test_fetch_reaction_returns_json_and_external_referer_is_never_used(client):
    uid = uuid.uuid4().hex[:8]
    email = f"fetch_user_{uid}@exemplo.mz"
    user_id = f"user_fetch_{uid}"
    db.create_user(user_id, email, hash_password("senha12345"), "Utilizador Fetch")
    client.post("/entrar", data={"email": email, "password": "senha12345"})

    post_id = uuid.uuid4().hex
    db.create_post(
        post_id,
        user_id,
        None,
        PostInput(
            theme="Produto público",
            business="Produto público",
            publisher_type=PublisherType.INDIVIDUAL,
            target_audience="Todos",
            objective="Vender",
            tone="casual",
            call_to_action="Contacta-me",
            contact="849998877",
        ),
    )
    db.update_status(post_id, db.PostStatus.COMPLETED)

    fetched = client.post(
        f"/posts/{post_id}/react",
        data={"type": "like"},
        headers={"X-Requested-With": "BoladasFetch"},
    )
    assert fetched.status_code == 200
    assert fetched.json()["likes"] == 1

    form = client.post(
        f"/posts/{post_id}/comments",
        data={"body": "Seguro", "return_to": "https://evil.example/roubar"},
        headers={"referer": "https://evil.example/roubar"},
        follow_redirects=False,
    )
    assert form.status_code == 303
    assert form.headers["location"] == f"/posts/{post_id}"
