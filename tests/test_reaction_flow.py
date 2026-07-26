import uuid
from unittest.mock import patch
from fastapi.testclient import TestClient

from app import db
from app.auth import hash_password
from app.main import app
from app.models import PostInput, PublisherType
from app.storage import UploadedFile

client = TestClient(app)


def _fake_upload(key, data, content_type):
    return UploadedFile(
        key=key,
        content_type=content_type,
        size=len(data),
        sha256="1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        url=f"https://fake-b2.example/{key}",
    )


@patch("app.routers.posts.upload_and_verify", side_effect=_fake_upload)
def test_full_interface_flow_reactions_and_comments(mock_upload):
    uid = uuid.uuid4().hex[:8]
    email = f"react_user_{uid}@exemplo.mz"
    user_id = f"user_react_{uid}"
    db.create_user(user_id, email, hash_password("senha12345"), "Utilizador Reação Teste")

    test_c = TestClient(app)
    test_c.post("/entrar", data={"email": email, "password": "senha12345"})

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
    resp_like = test_c.post(
        f"/posts/{post_id}/react",
        data={"type": "like"},
        headers={"referer": "http://testserver/explorar"},
        follow_redirects=False,
    )
    assert resp_like.status_code == 303, f"Falhou com status {resp_like.status_code}: {resp_like.text}"

    # 3. Testar dislike por formulário HTML (type="dislike", reason="Motivo claro") -> DEVE responder 303!
    resp_dislike = test_c.post(
        f"/posts/{post_id}/react",
        data={"type": "dislike", "reason": "Preço muito elevado para o estado real"},
        headers={"referer": "http://testserver/explorar"},
        follow_redirects=False,
    )
    assert resp_dislike.status_code == 303

    # 4. Testar comentário por formulário HTML -> DEVE responder 303!
    resp_comment = test_c.post(
        f"/posts/{post_id}/comments",
        data={"body": "Ainda está disponível em Maputo?"},
        headers={"referer": "http://testserver/explorar"},
        follow_redirects=False,
    )
    assert resp_comment.status_code == 303

    # 5. Confirmar que o comentário foi gravado
    comments = db.get_post_comments(post_id)
    assert len(comments) == 1
    assert comments[0]["body"] == "Ainda está disponível em Maputo?"
