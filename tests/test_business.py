import pytest
from fastapi.testclient import TestClient

from app import db as db_module


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


def _create_business(client, name, category="farmacia_saude"):
    resp = client.post(
        "/empresa/nova",
        data={"name": name, "category": category, "contact": "871234567"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    return resp.headers["location"].rsplit("/", 1)[-1]


def test_user_can_register_multiple_businesses(client):
    user = _register(client, "dono@exemplo.co.mz", "Dono")
    _create_business(client, "Farmácia Central", "farmacia_saude")
    _create_business(client, "Mecânica do Dono", "mecanica_automovel")

    businesses = db_module.list_businesses_by_user(user["user_id"])
    assert len(businesses) == 2
    names = {b["name"] for b in businesses}
    assert names == {"Farmácia Central", "Mecânica do Dono"}


def test_business_list_page_shows_all_businesses(client):
    _register(client, "dono2@exemplo.co.mz", "Dono2")
    _create_business(client, "Loja A")
    _create_business(client, "Loja B")

    resp = client.get("/empresa")
    assert resp.status_code == 200
    assert "Loja A" in resp.text
    assert "Loja B" in resp.text


def test_create_post_as_specific_business(client):
    user = _register(client, "dono3@exemplo.co.mz", "Dono3")
    biz_id = _create_business(client, "Farmácia do Bairro", "farmacia_saude")

    resp = client.post(
        "/posts",
        data={
            "publish_as": biz_id,
            "business": "Paracetamol 500mg",
            "category": "farmacia_saude",
            "target_audience": "Clientes locais",
            "objective": "Vender",
            "tone": "profissional",
            "language": "pt",
            "call_to_action": "Vem à farmácia",
            "contact": "871234567",
        },
    )
    # sem GMI_API_KEY real no ambiente de teste, a geração falha honestamente,
    # mas o post tem de ter sido criado já ligado à empresa certa
    assert resp.status_code in (200, 502)
    post_id = resp.json()["post_id"]
    post = db_module.get_post(post_id)
    assert post["business_id"] == biz_id
    assert post["brand_name"] == "Farmácia do Bairro"
    assert post["publisher_type"] == "business"


def test_create_post_rejects_business_not_owned(client):
    other = _register(client, "outro@exemplo.co.mz", "Outro")
    other_biz_id = _create_business(client, "Empresa do Outro")
    client.post("/sair", follow_redirects=False)

    _register(client, "atacante@exemplo.co.mz", "Atacante")
    resp = client.post(
        "/posts",
        data={
            "publish_as": other_biz_id,
            "business": "Produto suspeito",
            "category": "outro",
            "target_audience": "Todos",
            "objective": "Vender",
            "tone": "neutro",
            "language": "pt",
            "call_to_action": "Compra",
            "contact": "871234567",
        },
    )
    assert resp.status_code == 422
    assert "inválida" in resp.json()["error"]


def test_custom_category_is_accepted_and_preserves_label(client):
    user = _register(client, "custom@exemplo.co.mz", "Custom")
    resp = client.post(
        "/posts",
        data={
            "publish_as": "individual",
            "business": "Aulas de yoga",
            "category": "outro",
            "category_custom": "Bem-estar & Yoga",
            "target_audience": "Todos",
            "objective": "Vender",
            "tone": "neutro",
            "language": "pt",
            "call_to_action": "Inscreve-te",
            "contact": "871234567",
        },
    )
    post_id = resp.json()["post_id"]
    post = db_module.get_post(post_id)
    assert post["category"] == "Bem-estar & Yoga"


def test_business_edit_requires_ownership(client):
    _register(client, "dono4@exemplo.co.mz", "Dono4")
    biz_id = _create_business(client, "Negócio Privado")
    client.post("/sair", follow_redirects=False)

    _register(client, "intruso2@exemplo.co.mz", "Intruso2")
    resp = client.get(f"/empresa/{biz_id}/editar", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/empresa"


def test_suggest_category_endpoint_without_gmi_key_returns_unavailable(client, monkeypatch):
    from app import category_classify

    monkeypatch.setattr(category_classify, "GMI_API_KEY", None)
    _register(client, "sugestao@exemplo.co.mz", "Sugestao")

    resp = client.post("/categoria/sugerir", data={"description": "Vendo bolos e doces"})
    assert resp.status_code == 503
    assert "error" in resp.json()


def test_suggest_category_endpoint_requires_session(client):
    resp = client.post("/categoria/sugerir", data={"description": "Vendo bolos"})
    assert resp.status_code == 401
