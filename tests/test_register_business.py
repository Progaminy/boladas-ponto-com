import pytest
from fastapi.testclient import TestClient

from app import db as db_module


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    from app.main import app

    with TestClient(app) as c:
        yield c


def _payload(**overrides):
    dados = {
        "business_name": "Farmácia Central",
        "category": "farmacia_saude",
        "business_contact": "+258840000000",
        "location": "Maputo, Baixa",
        "description": "Medicamentos e produtos de saúde",
        "responsible_name": "Ana Responsável",
        "email": "ana@farmaciacentral.co.mz",
        "password": "password123",
        "terms_accepted": "on",
    }
    dados.update(overrides)
    return dados


def test_form_is_public(client):
    resp = client.get("/registar/empresa")
    assert resp.status_code == 200
    assert "Registar a minha empresa" in resp.text


def test_creates_account_and_business_in_one_step(client):
    resp = client.post("/registar/empresa", data=_payload(), follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/negocio/")

    user = db_module.get_user_by_email("ana@farmaciacentral.co.mz")
    assert user is not None
    assert user["terms_accepted_at"]

    empresas = db_module.list_businesses_by_user(user["user_id"])
    assert len(empresas) == 1
    assert empresas[0]["name"] == "Farmácia Central"
    assert empresas[0]["category"] == "farmacia_saude"

    # fica autenticado e como proprietário, sem ter de entrar outra vez
    assert db_module.is_business_owner(empresas[0]["business_id"], user["user_id"])
    assert client.get("/criar").status_code == 200


def test_custom_category_is_preserved(client):
    client.post(
        "/registar/empresa",
        data=_payload(category_custom="Barraca de Mercado Informal"),
        follow_redirects=False,
    )
    user = db_module.get_user_by_email("ana@farmaciacentral.co.mz")
    empresa = db_module.list_businesses_by_user(user["user_id"])[0]
    assert empresa["category"] == "Barraca de Mercado Informal"


def test_terms_are_required(client):
    payload = _payload()
    del payload["terms_accepted"]
    resp = client.post("/registar/empresa", data=payload, follow_redirects=False)
    assert resp.status_code == 422
    assert db_module.get_user_by_email("ana@farmaciacentral.co.mz") is None


def test_duplicate_email_explains_what_to_do_instead(client):
    client.post("/registar/empresa", data=_payload(), follow_redirects=False)
    resp = client.post(
        "/registar/empresa", data=_payload(business_name="Outra"), follow_redirects=False
    )
    assert resp.status_code == 409
    assert "Nova empresa" in resp.text

    user = db_module.get_user_by_email("ana@farmaciacentral.co.mz")
    assert len(db_module.list_businesses_by_user(user["user_id"])) == 1


def test_nothing_is_created_when_business_data_is_invalid(client):
    """A conta não pode ficar criada se a empresa falhar a validação."""
    resp = client.post(
        "/registar/empresa", data=_payload(business_contact="123"), follow_redirects=False
    )
    assert resp.status_code == 422
    assert db_module.get_user_by_email("ana@farmaciacentral.co.mz") is None
