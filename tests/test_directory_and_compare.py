import uuid

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    with TestClient(app) as test_client:
        yield test_client


def test_businesses_directory_lists_stores(client):
    response = client.get("/empresas")
    assert response.status_code == 200
    html = response.text
    assert "Ferragem Lendária Maputo" in html
    assert "Farmácia Moçambique Vida" in html
    assert "Moda &amp; Estilo Boutique" in html or "Moda & Estilo Boutique" in html
    assert "Mercado Popular de Xipamanine" in html
    assert "Transporte &amp; Carga Expresso" in html or "Transporte & Carga Expresso" in html


def test_compare_prices_and_proximity(client):
    client.post(
        "/registar",
        data={
            "email": f"compare-{uuid.uuid4().hex}@exemplo.co.mz",
            "password": "password123",
            "display_name": "Comprador",
            "terms_accepted": "on",
        },
        follow_redirects=False,
    )

    # Pesquisar cimento
    resp_cimento = client.get("/comparar?q=cimento")
    assert resp_cimento.status_code == 200
    assert "Cimento Limpopo" in resp_cimento.text

    # Pesquisar paracetamol
    resp_paracetamol = client.get("/comparar?q=paracetamol")
    assert resp_paracetamol.status_code == 200
    assert "Paracetamol 500mg" in resp_paracetamol.text

    # Testar ordenação por GPS com coordenadas de Maputo (-25.968, 32.573)
    resp_gps = client.get("/comparar?lat=-25.968&lon=32.573&sort=distance_asc")
    assert resp_gps.status_code == 200
    assert "km de distância (GPS)" in resp_gps.text


def test_inactive_posts_are_excluded_from_public_queries_and_counts(client):
    client.post(
        "/registar",
        data={
            "email": f"availability-{uuid.uuid4().hex}@exemplo.co.mz",
            "password": "password123",
            "display_name": "Comprador",
            "terms_accepted": "on",
        },
        follow_redirects=False,
    )

    before = {
        row["business_id"]: row["product_count"]
        for row in db.list_all_businesses()
    }
    assert before["biz_seed_ferragem"] == 3

    db.update_listing_status("post_seed_cimento", "paused")

    assert all(
        row["post_id"] != "post_seed_cimento"
        for row in db.list_public_posts()
    )
    assert all(
        row["post_id"] != "post_seed_cimento"
        for row in db.list_posts_by_business("biz_seed_ferragem")
    )
    assert all(
        row["post_id"] != "post_seed_cimento"
        for row in db.compare_prices_and_proximity(search_query="cimento")
    )

    response = client.get("/comparar?q=cimento")
    assert response.status_code == 200
    assert "Cimento Limpopo" not in response.text

    after = {
        row["business_id"]: row["product_count"]
        for row in db.list_all_businesses()
    }
    assert after["biz_seed_ferragem"] == 2
