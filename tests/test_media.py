import io
import subprocess

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import db as db_module
from app.media_validate import (
    MediaValidationError,
    ffprobe_available,
    validate_photo,
    validate_video,
)
from app.models import PostInput, PublisherType


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


def _sample_jpeg_bytes(size=(400, 400)) -> bytes:
    img = Image.new("RGB", size, color=(10, 20, 30))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_video_bytes(duration_seconds: float) -> bytes:
    if not ffprobe_available():
        pytest.skip("ffmpeg/ffprobe indisponível neste ambiente")
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", f"color=c=blue:s=64x64:d={duration_seconds}",
                "-pix_fmt", "yuv420p", str(out),
            ],
            check=True, capture_output=True,
        )
        return out.read_bytes()


# --- validação pura (sem rede/servidor) --------------------------------------

def test_validate_photo_accepts_real_jpeg():
    validate_photo(_sample_jpeg_bytes(), "image/jpeg")


def test_validate_photo_rejects_bad_content_type():
    with pytest.raises(MediaValidationError):
        validate_photo(_sample_jpeg_bytes(), "application/pdf")


def test_validate_photo_rejects_non_image_bytes():
    with pytest.raises(MediaValidationError):
        validate_photo(b"isto nao e uma imagem", "image/jpeg")


@pytest.mark.skipif(not ffprobe_available(), reason="ffmpeg/ffprobe indisponível")
def test_validate_video_accepts_short_video():
    data = _make_video_bytes(2)
    duration = validate_video(data, "video/mp4")
    assert 0 < duration <= 5


@pytest.mark.skipif(not ffprobe_available(), reason="ffmpeg/ffprobe indisponível")
def test_validate_video_rejects_too_long_video():
    data = _make_video_bytes(35)
    with pytest.raises(MediaValidationError, match="máximo"):
        validate_video(data, "video/mp4")


# --- fluxo HTTP completo (com backend B2 simulado) ---------------------------

class FakeMeta:
    def __init__(self, size):
        self.size = size


class FakeBackend:
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
        return self.objects[key]

    def get_durable_url(self, key):
        return f"https://fake-b2.example/{key}"


def test_media_upload_enforces_max_four_photos(client, monkeypatch):
    from app import storage

    fake = FakeBackend()
    monkeypatch.setattr(storage, "get_backend", lambda: fake)

    user = _register(client, "media@exemplo.co.mz", "MediaUser")
    db_module.create_post("post-media-1", user["user_id"], None, _dummy_post_input())

    files = [
        ("photos", (f"foto{i}.jpg", _sample_jpeg_bytes(), "image/jpeg")) for i in range(5)
    ]
    resp = client.post("/posts/post-media-1/media", files=files)
    assert resp.status_code == 422
    assert "4 fotos" in resp.text

    media = db_module.list_product_media("post-media-1")
    assert media == []


def test_media_upload_success_stores_photos(client, monkeypatch):
    from app import storage

    fake = FakeBackend()
    monkeypatch.setattr(storage, "get_backend", lambda: fake)

    user = _register(client, "media2@exemplo.co.mz", "MediaUser2")
    db_module.create_post("post-media-2", user["user_id"], None, _dummy_post_input())

    files = [("photos", ("foto.jpg", _sample_jpeg_bytes(), "image/jpeg"))]
    resp = client.post("/posts/post-media-2/media", files=files, follow_redirects=False)
    assert resp.status_code == 303

    media = db_module.list_product_media("post-media-2")
    assert len(media) == 1
    assert media[0]["media_type"] == "photo"
    assert media[0]["sha256"]


def test_media_upload_rejects_when_not_owner(client, monkeypatch):
    from app import storage

    fake = FakeBackend()
    monkeypatch.setattr(storage, "get_backend", lambda: fake)

    owner = _register(client, "dono@exemplo.co.mz", "Dono")
    db_module.create_post("post-media-3", owner["user_id"], None, _dummy_post_input())
    client.post("/sair", follow_redirects=False)

    _register(client, "intruso@exemplo.co.mz", "Intruso")
    files = [("photos", ("foto.jpg", _sample_jpeg_bytes(), "image/jpeg"))]
    resp = client.post("/posts/post-media-3/media", files=files, follow_redirects=False)
    assert resp.status_code == 303
    assert db_module.list_product_media("post-media-3") == []
