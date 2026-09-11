import uuid
import pytest
from fastapi.testclient import TestClient
from app import db
from app.auth import hash_password
from app.main import app

@pytest.fixture
def auth_client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    uid = uuid.uuid4().hex[:8]
    user_id = f"test_user_adv_{uid}"
    email = f"advanced_{uid}@exemplo.mz"
    with TestClient(app) as c:
        db.create_user(user_id, email, hash_password("senha12345"), "Utilizador Avançado")
        c.post("/entrar", data={"email": email, "password": "senha12345"})
        yield c, user_id

def create_manual(c, business="Item de teste"):
    return c.post("/posts", data={"business":business,"publish_as":"individual","contact":"841234567","price_mt":"1500","description":"Produto usado em bom estado."})

def test_individual_post_is_manual_and_completed(auth_client):
    c,_=auth_client
    r=create_manual(c,"Telemóvel usado")
    assert r.status_code==200
    p=db.get_post(r.json()["post_id"])
    assert p["status"]=="completed" and p["category"]=="venda_informal" and p["description_source"]=="manual"

def test_comments_likes_and_edit(auth_client):
    c,_=auth_client
    post_id=create_manual(c).json()["post_id"]
    assert c.post(f"/posts/{post_id}/react",data={"reaction_type":"like"}).status_code==200
    assert c.post(f"/posts/{post_id}/comments",data={"body":"Excelente"}).status_code==200
    edit=c.post(f"/posts/{post_id}/editar",data={"theme":"Item Editado","price_mt":"2500","contact":"879998877","location":"Maputo","description":"Editado"},follow_redirects=False)
    assert edit.status_code==303 and db.get_post(post_id)["theme"]=="Item Editado"

def test_seasonal_theme_setting(auth_client):
    c,user_id=auth_client
    assert c.post("/perfil/tema",data={"theme":"natal"},follow_redirects=False).status_code==303
    assert db.get_user_by_id(user_id)["seasonal_theme"]=="natal"
