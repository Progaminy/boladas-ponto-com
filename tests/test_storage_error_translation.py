import pytest
from app import storage

class FakeMeta:
    def __init__(self,size): self.size=size

class BackendSemPermissao:
    def put(self,key,data,content_type=None,**kwargs): raise RuntimeError("not entitled")
    def head(self,key,**kwargs): return None
    def get(self,key,**kwargs): raise AssertionError
    def get_durable_url(self,key): return ""

def test_erro_do_backend_vira_storage_error(monkeypatch):
    monkeypatch.setattr(storage,"get_backend",lambda:BackendSemPermissao())
    with pytest.raises(storage.StorageError) as exc:
        storage.upload_and_verify("users/u1/profile.jpg",b"dados","image/jpeg")
    assert "not entitled" in str(exc.value)

def test_hash_incorreto_e_detectado(monkeypatch):
    class Backend:
        def put(self,key,data,content_type=None,**kwargs): return key
        def head(self,key,**kwargs): return FakeMeta(5)
        def get(self,key,**kwargs): return b"XXXXX"
        def get_durable_url(self,key): return ""
    monkeypatch.setattr(storage,"get_backend",lambda:Backend())
    with pytest.raises(storage.StorageError,match="SHA-256"):
        storage.upload_and_verify("posts/p1/foto.jpg",b"dados","image/jpeg")
