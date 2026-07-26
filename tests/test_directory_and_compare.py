from fastapi.testclient import TestClient

from app import db
from app.main import app

client = TestClient(app)


def test_businesses_directory_lists_stores():
    # Inicializa BD se necessário
    db.init_db()

    response = client.get("/empresas")
    assert response.status_code == 200
    html = response.text
    assert "Ferragem Lendária Maputo" in html
    assert "Farmácia Moçambique Vida" in html
    assert "Moda &amp; Estilo Boutique" in html or "Moda & Estilo Boutique" in html
    assert "Mercado Popular de Xipamanine" in html
    assert "Transporte &amp; Carga Expresso" in html or "Transporte & Carga Expresso" in html


def test_compare_prices_and_proximity():
    db.init_db()

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
