import pytest
from fastapi.testclient import TestClient

from app import db as db_module
from app.models import PostInput, PublisherType


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    from app.main import app
    from app.routers import posts as posts_router

    monkeypatch.setattr(posts_router, "MAX_POSTS_PER_USER_PER_DAY", 2)

    with TestClient(app) as c:
        yield c


def _dummy_post_input() -> PostInput:
    return PostInput(
        theme="Tema",
        business="Negócio",
        category="outro",
        publisher_type=PublisherType.INDIVIDUAL,
        target_audience="Todos",
        objective="Vender",
        tone="neutro",
        call_to_action="Compra",
        contact="871234567",
    )


def test_create_post_blocked_after_daily_limit(client):
    client.post(
        "/registar",
        data={"email": "limite@exemplo.co.mz", "password": "password123", "display_name": "Limite"},
        follow_redirects=False,
    )
    user = db_module.get_user_by_email("limite@exemplo.co.mz")

    for i in range(2):
        db_module.create_post(f"post-{i}", user["user_id"], None, _dummy_post_input())

    resp = client.post(
        "/posts",
        data={
            "theme": "Mais um",
            "business": "Loja",
            "category": "outro",
            "publisher_type": "individual",
            "target_audience": "Todos",
            "objective": "Vender",
            "tone": "amigável",
            "language": "pt",
            "call_to_action": "Compra já",
            "contact": "871234567",
        },
    )
    assert resp.status_code == 429
    assert "Limite" in resp.json()["error"]
