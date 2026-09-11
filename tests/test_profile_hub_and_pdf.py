import uuid
import pytest
from fastapi.testclient import TestClient
from app import db as db_module
from app.models import PostInput, PostStatus, PublisherType

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(db_module,"DB_PATH",tmp_path/"test.db")
    from app.main import app
    with TestClient(app) as c: yield c

def test_profile_tabs_are_manual_marketplace(client):
    client.post("/registar",data={"email":"gestor@exemplo.co.mz","password":"segredo-forte-123","display_name":"Gestor","terms_accepted":"on"})
    resp=client.get("/perfil",follow_redirects=False)
    assert resp.status_code==303
    page=client.get(resp.headers["location"])
    assert page.status_code==200 and "Produtos & Anúncios" in page.text and "gerar imagem" not in page.text.lower()

def test_listing_status_and_pdf(client):
    client.post("/registar",data={"email":"vendedor@exemplo.co.mz","password":"segredo-forte-123","display_name":"Vendedor","terms_accepted":"on"})
    seller=db_module.get_user_by_email("vendedor@exemplo.co.mz")
    post_id=f"post-{uuid.uuid4().hex}"
    data=PostInput(theme="Gerador Diesel 5kW",business="Ferragem",category="ferragens",publisher_type=PublisherType.INDIVIDUAL,target_audience="Clientes",objective="Publicar anúncio",tone="direto",call_to_action="Contactar vendedor",price_mt=45000,currency="MZN",contact="841234567",location="Maputo",description="Gerador novo")
    db_module.create_post(post_id,seller["user_id"],None,data); db_module.update_status(post_id,PostStatus.COMPLETED)
    assert client.post(f"/posts/{post_id}/estado",data={"new_status":"paused"},follow_redirects=False).status_code==303
    pdf=client.get(f"/posts/{post_id}/fatura.pdf")
    assert pdf.status_code==200 and pdf.headers["content-type"]=="application/pdf" and b"%PDF" in pdf.content[:10]
