import pytest
from fastapi.testclient import TestClient

from app import db as db_module
from app.diagnostics import check_b2, check_gmicloud


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_b2_reports_not_configured_without_credentials(monkeypatch):
    from app import diagnostics

    monkeypatch.setattr(diagnostics, "b2_configured", lambda: False)
    check = check_b2()
    assert check.state == "not_configured"
    assert check.ok is False
    assert "B2_KEY_ID" in check.detail


def test_b2_reports_failure_with_real_error_message(monkeypatch):
    from app import diagnostics, storage

    monkeypatch.setattr(diagnostics, "b2_configured", lambda: True)

    class BrokenBackend:
        def head(self, key, **kwargs):
            raise RuntimeError("credenciais inválidas")

    monkeypatch.setattr(storage, "get_backend", lambda: BrokenBackend())
    check = check_b2()
    assert check.state == "failing"
    # o erro real do serviço tem de aparecer, não uma mensagem genérica
    assert "credenciais inválidas" in check.detail


def test_gmicloud_reports_not_configured_without_key(monkeypatch):
    from app import diagnostics

    monkeypatch.setattr(diagnostics, "gmi_configured", lambda: False)
    check = check_gmicloud()
    assert check.state == "not_configured"
    assert "GMI_API_KEY" in check.detail


def test_gmicloud_reports_rejected_key(monkeypatch):
    from app import diagnostics

    monkeypatch.setattr(diagnostics, "gmi_configured", lambda: True)

    class FakeResponse:
        status_code = 401

    import httpx

    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse())
    check = check_gmicloud()
    assert check.state == "failing"
    assert "401" in check.detail


def test_gmicloud_ok_still_warns_that_key_is_not_balance(monkeypatch):
    from app import diagnostics

    monkeypatch.setattr(diagnostics, "gmi_configured", lambda: True)

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"data": [{"id": "seedream-5.0-lite"}, {"id": "deepseek-ai/DeepSeek-V3-0324"}]}

    import httpx

    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse())
    check = check_gmicloud()
    assert check.state == "ok"
    # não deve dar a entender que há saldo garantido
    assert "saldo" in check.detail


def test_status_page_renders_without_session(client):
    resp = client.get("/estado")
    assert resp.status_code == 200
    assert "Estado do sistema" in resp.text
    assert "Backblaze B2" in resp.text
    assert "GMICloud" in resp.text


def test_health_endpoint_does_not_contact_external_services(client, monkeypatch):
    """O health-check do Render tem de ser barato e não falhar por causa de
    uma dependência externa em baixo."""
    from app import diagnostics

    def explode():
        raise AssertionError("/health não pode correr diagnósticos externos")

    monkeypatch.setattr(diagnostics, "run_all_checks", explode)

    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["app"] == "Boladas-ponto-com"
