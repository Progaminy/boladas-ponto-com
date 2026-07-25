import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import db as db_module


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    from app.main import app

    with TestClient(app) as c:
        yield c


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


def _register(client, email, name="Nome"):
    client.post(
        "/registar",
        data={"email": email, "password": "password123", "display_name": name, "terms_accepted": "on"},
        follow_redirects=False,
    )
    return db_module.get_user_by_email(email)


def _sample_jpeg_bytes() -> bytes:
    img = Image.new("RGB", (200, 200), color=(50, 60, 70))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_user_can_upload_profile_and_cover_photo(client, monkeypatch):
    from app import storage

    fake = FakeBackend()
    monkeypatch.setattr(storage, "get_backend", lambda: fake)

    user = _register(client, "foto@exemplo.co.mz", "FotoUser")
    resp = client.post(
        "/perfil/fotos",
        files={
            "profile_photo": ("perfil.jpg", _sample_jpeg_bytes(), "image/jpeg"),
            "cover_photo": ("capa.jpg", _sample_jpeg_bytes(), "image/jpeg"),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303

    row = db_module.get_user_by_id(user["user_id"])
    assert row["profile_photo_url"]
    assert row["cover_photo_url"]

    profile_page = client.get(f"/utilizador/{user['user_id']}")
    assert profile_page.status_code == 200
    assert "FotoUser" in profile_page.text


def test_business_photo_upload_requires_ownership(client, monkeypatch):
    from app import storage

    fake = FakeBackend()
    monkeypatch.setattr(storage, "get_backend", lambda: fake)

    _register(client, "dono@exemplo.co.mz", "Dono")
    resp = client.post(
        "/empresa/nova", data={"name": "Loja", "category": "outro", "contact": "871234567"},
        follow_redirects=False,
    )
    biz_id = resp.headers["location"].rsplit("/", 1)[-1]
    client.post("/sair", follow_redirects=False)

    _register(client, "intruso@exemplo.co.mz", "Intruso")
    resp = client.post(
        f"/empresa/{biz_id}/fotos",
        files={"profile_photo": ("p.jpg", _sample_jpeg_bytes(), "image/jpeg")},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/empresa"

    biz = db_module.get_business(biz_id)
    assert biz["profile_photo_url"] is None
