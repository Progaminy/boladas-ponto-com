"""Erros do backend B2 devem chegar aos chamadores como StorageError."""

import pytest

from app import storage


class FakeMeta:
    def __init__(self, size):
        self.size = size


class BackendSemPermissao:
    def put(self, key, data, content_type=None, **kwargs):
        raise RuntimeError(f"Storage put for {key!r} failed: not entitled")

    def head(self, key, **kwargs):
        return None

    def get(self, key, **kwargs):
        raise AssertionError("não devia chegar aqui")

    def get_durable_url(self, key):
        return f"https://fake-b2.example/{key}"


def test_recusa_do_backend_vira_storage_error(monkeypatch):
    monkeypatch.setattr(storage, "get_backend", lambda: BackendSemPermissao())

    with pytest.raises(storage.StorageError) as exc:
        storage.upload_and_verify("users/u1/profile.jpg", b"dados", "image/jpeg")

    assert "not entitled" in str(exc.value)
    assert "users/u1/profile.jpg" in str(exc.value)


def test_a_nossa_storage_error_nao_e_reembrulhada(monkeypatch):
    class BackendQueCorrompe:
        def put(self, key, data, content_type=None, **kwargs):
            return key

        def head(self, key, **kwargs):
            return FakeMeta(size=5)

        def get(self, key, **kwargs):
            return b"XXXXX"

        def get_durable_url(self, key):
            return f"https://fake-b2.example/{key}"

    monkeypatch.setattr(storage, "get_backend", lambda: BackendQueCorrompe())

    with pytest.raises(storage.StorageError, match="SHA-256"):
        storage.upload_and_verify("posts/p1/image.png", b"dados", "image/png")


def test_erro_inesperado_do_backend_tambem_e_traduzido(monkeypatch):
    class BackendQueExplode:
        def put(self, key, data, content_type=None, **kwargs):
            raise RuntimeError("rede em baixo")

        def head(self, key, **kwargs):
            return None

        def get_durable_url(self, key):
            return ""

    monkeypatch.setattr(storage, "get_backend", lambda: BackendQueExplode())

    with pytest.raises(storage.StorageError, match="rede em baixo"):
        storage.upload_and_verify("posts/p1/image.png", b"dados", "image/png")
