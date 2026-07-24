import pytest

from app import storage


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

    def get_durable_url(self, key):
        return f"https://fake-b2.example/{key}"


def test_post_key_layout():
    assert storage.post_key("abc123", "image.png") == "posts/abc123/image.png"


def test_sha256_hex_matches_hashlib():
    import hashlib

    data = b"hello world"
    assert storage.sha256_hex(data) == hashlib.sha256(data).hexdigest()


def test_upload_and_verify_success(monkeypatch):
    fake = FakeBackend()
    monkeypatch.setattr(storage, "get_backend", lambda: fake)

    data = b"fake image bytes"
    result = storage.upload_and_verify("posts/x/image.png", data, "image/png")

    assert result.key == "posts/x/image.png"
    assert result.size == len(data)
    assert result.sha256 == storage.sha256_hex(data)
    assert result.url == "https://fake-b2.example/posts/x/image.png"


def test_upload_and_verify_raises_when_head_confirms_nothing(monkeypatch):
    class GhostBackend(FakeBackend):
        def put(self, key, data, content_type=None, **kwargs):
            return key  # "uploads" but never actually stores anything

        def head(self, key, **kwargs):
            return None

    monkeypatch.setattr(storage, "get_backend", lambda: GhostBackend())

    with pytest.raises(storage.StorageError):
        storage.upload_and_verify("posts/x/image.png", b"data", "image/png")


def test_upload_and_verify_raises_on_size_mismatch(monkeypatch):
    class CorruptingBackend(FakeBackend):
        def head(self, key, **kwargs):
            return FakeMeta(size=1)  # nunca corresponde ao que foi enviado

    monkeypatch.setattr(storage, "get_backend", lambda: CorruptingBackend())

    with pytest.raises(storage.StorageError):
        storage.upload_and_verify("posts/x/image.png", b"more than one byte", "image/png")
