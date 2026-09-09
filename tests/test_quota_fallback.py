import uuid
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app import db
from app.auth import hash_password
from app.main import app
from app.pipeline import GenerationError
from app.storage import UploadedFile

def _fake_upload(key, data, content_type):
    return UploadedFile(
        key=key,
        content_type=content_type,
        size=len(data),
        sha256="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        url=f"https://fake-b2.example/{key}",
    )


def _failing_generate_caption(*args, **kwargs):
    raise GenerationError(
        "Todos os provedores de texto configurados falharam. vertex: 429 RESOURCE_EXHAUSTED | gmicloud: 402 Insufficient balance"
    )


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    with TestClient(app) as test_client:
        yield test_client


@patch("app.routers.posts.generate_caption", side_effect=_failing_generate_caption)
@patch("app.routers.posts.upload_and_verify", side_effect=_fake_upload)
def test_quota_429_fallback_completes_post_and_stores_files_in_b2(
    mock_upload, mock_caption, client
):
    # Regista utilizador de teste
    uid = uuid.uuid4().hex[:8]
    user_id = f"test_user_quota_{uid}"
    email = f"quota_{uid}@exemplo.mz"
    pwd_hash = hash_password("senha12345")
    db.create_user(user_id, email, pwd_hash, "Vendedor Quota Teste")

    client.post("/entrar", data={"email": email, "password": "senha12345"})

    # Submeter post quando a IA de texto falhar por quota 429.
    # Não há gerador de imagem no fluxo de publicação.
    resp = client.post(
        "/posts",
        data={
            "business": "Telemóvel Usado Samsung A12",
            "publish_as": "individual",
            "contact": "841234567",
            "price_mt": "6500",
            "description": "Excelente estado, bateria duradoura.",
        },
    )

    # O post DEVE responder 200 OK (não 502/Failed!)
    assert resp.status_code == 200
    post_id = resp.json()["post_id"]

    post = db.get_post(post_id)
    assert post is not None
    assert post["status"] == "completed"
    assert post["caption"] == "Excelente estado, bateria duradoura."
    assert post["caption_key"] is not None
    assert post["provenance_key"] is not None
    assert post["image_key"] is None


def test_public_can_browse_the_feed_without_an_account(client):
    resp = client.get("/explorar", follow_redirects=False)
    assert resp.status_code == 200
