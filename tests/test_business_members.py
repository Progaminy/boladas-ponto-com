import pytest
from fastapi.testclient import TestClient

from app import db as db_module
from app.models import BusinessInput


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    from app.main import app

    with TestClient(app) as c:
        yield c


def _register(client, email, name):
    client.post(
        "/registar",
        data={"email": email, "password": "password123", "display_name": name,
              "terms_accepted": "on"},
        follow_redirects=False,
    )
    return db_module.get_user_by_email(email)


def _login(client, email):
    client.post(
        "/entrar", data={"email": email, "password": "password123"}, follow_redirects=False
    )


def _business_input(name="Farmácia Central"):
    return BusinessInput(
        name=name, category="farmacia_saude", description="Medicamentos",
        location="Maputo", contact="+258840000000",
    )


def _setup(client):
    """Proprietário com uma empresa, e um sócio ainda sem acesso."""
    owner = _register(client, "dono@exemplo.co.mz", "Dono")
    db_module.create_business("biz-1", owner["user_id"], _business_input())
    client.post("/sair", follow_redirects=False)
    socio = _register(client, "socio@exemplo.co.mz", "Sócio")
    client.post("/sair", follow_redirects=False)
    _login(client, "dono@exemplo.co.mz")
    return owner, socio


def test_creator_becomes_owner_automatically(client):
    owner, _ = _setup(client)
    assert db_module.get_business_role("biz-1", owner["user_id"]) == "proprietario"
    assert db_module.is_business_owner("biz-1", owner["user_id"])


def test_owner_can_add_partner_who_then_manages_the_business(client):
    owner, socio = _setup(client)

    resp = client.post(
        "/empresa/biz-1/gestores", data={"email": "socio@exemplo.co.mz"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert db_module.get_business_role("biz-1", socio["user_id"]) == "gestor"

    # o sócio passa a ver a empresa como sua e consegue editá-la
    client.post("/sair", follow_redirects=False)
    _login(client, "socio@exemplo.co.mz")

    nomes = [b["name"] for b in db_module.list_businesses_by_user(socio["user_id"])]
    assert "Farmácia Central" in nomes
    assert client.get("/empresa/biz-1/editar", follow_redirects=False).status_code == 200


def test_adding_unknown_email_reports_it_instead_of_failing_silently(client):
    _setup(client)
    resp = client.post(
        "/empresa/biz-1/gestores", data={"email": "ninguem@exemplo.co.mz"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "error=nao-encontrado" in resp.headers["location"]
    assert len(db_module.list_business_members("biz-1")) == 1


def test_partner_cannot_add_or_remove_other_managers(client):
    owner, socio = _setup(client)
    client.post("/empresa/biz-1/gestores", data={"email": "socio@exemplo.co.mz"},
                follow_redirects=False)
    client.post("/sair", follow_redirects=False)

    outro = _register(client, "outro@exemplo.co.mz", "Outro")
    client.post("/sair", follow_redirects=False)
    _login(client, "socio@exemplo.co.mz")

    client.post("/empresa/biz-1/gestores", data={"email": "outro@exemplo.co.mz"},
                follow_redirects=False)
    assert db_module.get_business_role("biz-1", outro["user_id"]) is None

    client.post(f"/empresa/biz-1/gestores/{owner['user_id']}/remover", follow_redirects=False)
    assert db_module.is_business_owner("biz-1", owner["user_id"])


def test_owner_cannot_be_removed_even_by_themselves(client):
    """Uma empresa sem proprietário ficaria órfã e inacessível."""
    owner, _ = _setup(client)
    db_module.remove_business_member("biz-1", owner["user_id"])
    assert db_module.is_business_owner("biz-1", owner["user_id"])


def test_owner_can_remove_a_partner(client):
    owner, socio = _setup(client)
    client.post("/empresa/biz-1/gestores", data={"email": "socio@exemplo.co.mz"},
                follow_redirects=False)
    assert db_module.get_business_role("biz-1", socio["user_id"]) == "gestor"

    resp = client.post(
        f"/empresa/biz-1/gestores/{socio['user_id']}/remover", follow_redirects=False
    )
    assert resp.status_code == 303
    assert db_module.get_business_role("biz-1", socio["user_id"]) is None


def test_non_member_cannot_see_managers_page(client):
    _setup(client)
    client.post("/sair", follow_redirects=False)
    _register(client, "estranho@exemplo.co.mz", "Estranho")

    resp = client.get("/empresa/biz-1/gestores", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/empresa"
