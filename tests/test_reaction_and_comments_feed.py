"""Testes automatizados para Reações (Likes/Dislikes) e Comentários no Feed Social.
"""

import pytest
from fastapi.testclient import TestClient
from app import db as db_module


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_feed_reactions_and_comments_flow(client):
    # 1. Registar utilizadores
    client.post(
        "/registar",
        data={
            "auth_method": "email",
            "email": "user1@exemplo.co.mz",
            "password": "segredo-forte-123",
            "display_name": "Ana Maria",
            "terms_accepted": "on",
        },
    )

    # 2. Criar post
    post_resp = client.post(
        "/posts",
        data={
            "theme": "Computador Portátil HP i7 16GB RAM",
            "business": "Loja Tech Moz",
            "category": "tecnologia",
            "publish_as": "individual",
            "price_mt": "35000",
            "currency": "MZN",
            "contact": "841112233",
            "location": "Maputo",
            "description": "Portátil seminovos com garantia de 6 meses",
        },
    )
    assert post_resp.status_code in (200, 502)
    post_id = post_resp.json()["post_id"]
    db_module.update_status(post_id, "completed")

    # 3. Dar Like no post no feed
    like_resp = client.post(
        f"/posts/{post_id}/react",
        data={"type": "like"},
        follow_redirects=True,
    )
    assert like_resp.status_code == 200

    # Verificar se o Like aparece no feed
    feed_resp = client.get("/explorar")
    assert feed_resp.status_code == 200
    assert "1 Gostar" in feed_resp.text

    # 4. Adicionar um Comentário no feed
    comment_resp = client.post(
        f"/posts/{post_id}/comments",
        data={"body": "Ainda está disponível para entrega hoje?"},
        follow_redirects=True,
    )
    assert comment_resp.status_code == 200

    # Verificar se o comentário e a contagem aparecem diretamente no feed
    feed_after_comment = client.get("/explorar")
    assert feed_after_comment.status_code == 200
    assert "💬 Comentários (1)" in feed_after_comment.text
    assert "Ainda está disponível para entrega hoje?" in feed_after_comment.text
    assert "Ana Maria" in feed_after_comment.text

    # 5. Clicar novamente em Like para testar o Toggle Off (desfazer like)
    toggle_like = client.post(
        f"/posts/{post_id}/react",
        data={"type": "like"},
        follow_redirects=True,
    )
    assert toggle_like.status_code == 200

    feed_after_toggle = client.get("/explorar")
    assert feed_after_toggle.status_code == 200
    assert "0 Gostar" in feed_after_toggle.text
