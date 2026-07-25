import json

import pytest
from fastapi.testclient import TestClient

from app import db as db_module
from app.models import PostInput, PublisherType
from app.verify import verify_post_files


class FakeMeta:
    def __init__(self, size):
        self.size = size


class FakeBackend:
    """Backend B2 simulado cujo conteúdo pode ser adulterado a meio do teste,
    para provar que a verificação apanha alterações reais."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def put(self, key, data, content_type=None, **kwargs):
        self.objects[key] = data
        return key

    def head(self, key, **kwargs):
        if key not in self.objects:
            return None
        return FakeMeta(size=len(self.objects[key]))

    def get(self, key, **kwargs):
        if key not in self.objects:
            raise KeyError(f"objeto inexistente: {key}")
        return self.objects[key]

    def get_durable_url(self, key):
        return f"https://fake-b2.example/{key}"


IMAGE_BYTES = b"bytes da imagem gerada"
CAPTION_BYTES = b"legenda do post"

# hashes reais destes bytes, calculados pelo mesmo caminho de código da app
from app.storage import sha256_hex  # noqa: E402

PROVENANCE = {
    "post_id": "post-verify",
    "files": {
        "image": {"b2_key": "posts/post-verify/image.png", "sha256": sha256_hex(IMAGE_BYTES)},
        "caption": {"b2_key": "posts/post-verify/caption.txt", "sha256": sha256_hex(CAPTION_BYTES)},
    },
}


@pytest.fixture
def fake_b2(monkeypatch):
    """Substitui o backend B2 em todos os módulos que o importaram
    diretamente (`from app.storage import get_backend` cria uma referência
    própria em cada módulo, que um patch só em app.storage não alcança)."""
    from app import storage, verify
    from app.routers import provenance as provenance_router

    backend = FakeBackend()
    backend.put("posts/post-verify/image.png", IMAGE_BYTES)
    backend.put("posts/post-verify/caption.txt", CAPTION_BYTES)
    for module in (storage, verify, provenance_router):
        monkeypatch.setattr(module, "get_backend", lambda: backend)
    return backend


def test_verify_passes_when_files_are_intact(fake_b2):
    report = verify_post_files("post-verify", PROVENANCE)
    assert report.all_match is True
    assert report.checked_count == 2
    assert all(f.error is None for f in report.files)


def test_verify_detects_tampered_file(fake_b2):
    # alguém substitui a imagem no bucket, mantendo a chave
    fake_b2.objects["posts/post-verify/image.png"] = b"imagem completamente diferente"

    report = verify_post_files("post-verify", PROVENANCE)
    assert report.all_match is False

    image_result = next(f for f in report.files if f.name == "image")
    assert image_result.matches is False
    assert image_result.actual_sha256 != image_result.claimed_sha256

    # a legenda continua intacta — a verificação é por ficheiro, não tudo-ou-nada
    caption_result = next(f for f in report.files if f.name == "caption")
    assert caption_result.matches is True


def test_verify_reports_missing_file_honestly(fake_b2):
    del fake_b2.objects["posts/post-verify/caption.txt"]

    report = verify_post_files("post-verify", PROVENANCE)
    assert report.all_match is False

    caption_result = next(f for f in report.files if f.name == "caption")
    assert caption_result.matches is False
    assert caption_result.actual_sha256 is None
    assert "B2" in caption_result.error


def test_verify_ignores_entries_without_hash(fake_b2):
    provenance = {"files": {"thumbnail": {"b2_key": "posts/x/thumbnail.webp"}}}
    report = verify_post_files("post-verify", provenance)
    assert report.files == []
    assert report.all_match is False


# --- endpoint HTTP -----------------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    from app.main import app

    with TestClient(app) as c:
        yield c


def _seed_completed_post(client, fake_b2):
    client.post(
        "/registar",
        data={"email": "v@exemplo.co.mz", "password": "password123",
              "display_name": "Verificador", "terms_accepted": "on"},
        follow_redirects=False,
    )
    user = db_module.get_user_by_email("v@exemplo.co.mz")
    db_module.create_post(
        "post-verify", user["user_id"], None,
        PostInput(
            theme="Teste", business="Produto", category="outro",
            publisher_type=PublisherType.INDIVIDUAL, target_audience="Todos",
            objective="Vender", tone="neutro", call_to_action="Compra",
            contact="871234567",
        ),
    )
    prov_key = "posts/post-verify/provenance.json"
    fake_b2.put(prov_key, json.dumps(PROVENANCE).encode("utf-8"))
    db_module.save_generation_result(
        "post-verify", caption="c", call_to_action_generated="cta", hashtags=["a"],
        image_key="posts/post-verify/image.png", caption_key="posts/post-verify/caption.txt",
        provenance_key=prov_key, thumbnail_key=None, image_url="https://fake-b2.example/img",
    )
    db_module.update_status("post-verify", db_module.PostStatus.COMPLETED)


def test_verify_endpoint_returns_match_report(client, fake_b2):
    _seed_completed_post(client, fake_b2)

    resp = client.post("/posts/post-verify/verificar")
    assert resp.status_code == 200
    data = resp.json()
    assert data["all_match"] is True
    assert data["checked_count"] == 2
    assert data["verified_at"]


def test_verify_endpoint_flags_tampering(client, fake_b2):
    _seed_completed_post(client, fake_b2)
    fake_b2.objects["posts/post-verify/image.png"] = b"adulterado"

    resp = client.post("/posts/post-verify/verificar")
    assert resp.status_code == 200
    data = resp.json()
    assert data["all_match"] is False
    image = next(f for f in data["files"] if f["name"] == "image")
    assert image["matches"] is False


def test_verify_endpoint_is_public(client, fake_b2):
    """Os jurados têm de poder verificar sem criar conta."""
    _seed_completed_post(client, fake_b2)
    client.post("/sair", follow_redirects=False)

    resp = client.post("/posts/post-verify/verificar")
    assert resp.status_code == 200
    assert resp.json()["all_match"] is True


def test_verify_endpoint_404_for_unknown_post(client, fake_b2):
    resp = client.post("/posts/nao-existe/verificar")
    assert resp.status_code == 404
