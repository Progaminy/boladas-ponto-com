import pytest
from fastapi.testclient import TestClient
from urllib.parse import parse_qs, urlsplit

from app import auth
from app import db as db_module


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    from app.main import app

    with TestClient(app) as c:
        yield c


def assert_login_redirect(response, expected_next: str) -> None:
    assert response.status_code == 303
    location = urlsplit(response.headers["location"])
    assert location.path == "/entrar"
    assert parse_qs(location.query) == {"next": [expected_next]}


def test_hash_password_roundtrip():
    hashed = auth.hash_password("segredo-forte-123")
    assert hashed != "segredo-forte-123"
    assert auth.verify_password("segredo-forte-123", hashed)
    assert not auth.verify_password("errada", hashed)


def test_register_logs_in_and_redirects_to_explorar(client):
    resp = client.post(
        "/registar",
        data={"email": "ana@exemplo.co.mz", "password": "password123", "display_name": "Ana", "terms_accepted": "on"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/explorar"

    follow = client.get("/explorar")
    assert follow.status_code == 200
    assert "Feed" in follow.text


def test_register_without_accepting_terms_rejected(client):
    resp = client.post(
        "/registar",
        data={"email": "semtermos@exemplo.co.mz", "password": "password123", "display_name": "Sem Termos"},
        follow_redirects=False,
    )
    assert resp.status_code == 422
    assert db_module.get_user_by_email("semtermos@exemplo.co.mz") is None


def test_terms_page_accessible_without_session(client):
    resp = client.get("/termos")
    assert resp.status_code == 200
    assert "Termos de Uso" in resp.text


def test_register_duplicate_email_rejected(client):
    payload = {"email": "dup@exemplo.co.mz", "password": "password123", "display_name": "Dup", "terms_accepted": "on"}
    client.post("/registar", data=payload, follow_redirects=False)
    resp = client.post("/registar", data=payload, follow_redirects=False)
    assert resp.status_code == 409
    assert "Já existe" in resp.text


def test_login_wrong_password_rejected(client):
    client.post(
        "/registar",
        data={"email": "bob@exemplo.co.mz", "password": "password123", "display_name": "Bob", "terms_accepted": "on"},
        follow_redirects=False,
    )
    client.post("/sair", follow_redirects=False)

    resp = client.post(
        "/entrar", data={"email": "bob@exemplo.co.mz", "password": "errada"}, follow_redirects=False
    )
    assert resp.status_code == 401


def test_protected_routes_redirect_when_logged_out(client):
    for path in ["/criar", "/historico"]:
        resp = client.get(path, follow_redirects=False)
        assert_login_redirect(resp, path)

    # Esta rota pertence ao módulo de empresas, fora do fluxo alterado aqui.
    resp = client.get("/empresa", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/entrar"


def test_feed_and_comparator_are_public(client):
    """Ver o que se vende não exige conta: quem chega tem de poder avaliar a
    plataforma antes de se registar. O que exige sessão é agir — publicar,
    reagir, comentar, contactar."""
    assert client.get("/explorar", follow_redirects=False).status_code == 200
    assert client.get("/comparar", follow_redirects=False).status_code == 200


def test_login_returns_to_local_path_and_preserves_query(client):
    client.post(
        "/registar",
        data={
            "email": "retorno@exemplo.co.mz",
            "password": "password123",
            "display_name": "Retorno",
            "terms_accepted": "on",
        },
        follow_redirects=False,
    )
    client.post("/sair", follow_redirects=False)

    # rota que continua protegida: o feed e o comparador passaram a ser
    # públicos, por isso já não servem para testar o retorno após login
    destination = "/historico?estado=completed&pagina=2"
    protected = client.get(destination, follow_redirects=False)
    assert_login_redirect(protected, destination)

    login_page = client.get(protected.headers["location"])
    assert login_page.status_code == 200
    assert 'name="next"' in login_page.text
    assert 'value="/historico?estado=completed&amp;pagina=2"' in login_page.text

    logged_in = client.post(
        "/entrar",
        data={
            "identifier": "retorno@exemplo.co.mz",
            "password": "password123",
            "next": destination,
        },
        follow_redirects=False,
    )
    assert logged_in.status_code == 303
    assert logged_in.headers["location"] == destination


@pytest.mark.parametrize(
    "unsafe",
    [
        "https://evil.example/roubar",
        "//evil.example/roubar",
        r"/\\evil.example/roubar",
        "javascript:alert(1)",
        "/destino\nX-Header: injetado",
    ],
)
def test_safe_next_url_rejects_external_or_ambiguous_destinations(unsafe):
    assert auth.safe_next_url(unsafe) == "/explorar"


def test_login_post_cannot_redirect_to_external_site(client):
    client.post(
        "/registar",
        data={
            "email": "seguro@exemplo.co.mz",
            "password": "password123",
            "display_name": "Seguro",
            "terms_accepted": "on",
        },
        follow_redirects=False,
    )
    client.post("/sair", follow_redirects=False)

    resp = client.post(
        "/entrar",
        data={
            "identifier": "seguro@exemplo.co.mz",
            "password": "password123",
            "next": "https://evil.example/roubar",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/explorar"


def test_create_post_without_session_returns_401(client):
    valid_payload = {
        "theme": "Promoção",
        "business": "Loja X",
        "category": "outro",
        "publisher_type": "individual",
        "target_audience": "Todos",
        "objective": "Vender",
        "tone": "amigável",
        "language": "pt",
        "call_to_action": "Compra já",
        "contact": "871234567",
    }
    resp = client.post("/posts", data=valid_payload)
    assert resp.status_code == 401
    assert resp.json()["error"]


def test_post_result_and_provenance_public_without_session(client):
    # partilhável sem conta — devolve 404 real (não redireciona para /entrar)
    # porque o post não existe, mas a rota em si não exige sessão.
    resp = client.get("/posts/inexistente", follow_redirects=False)
    assert resp.status_code == 404

    resp = client.get("/posts/inexistente/provenance", follow_redirects=False)
    assert resp.status_code == 404


def test_explorar_accessible_for_logged_in_user(client):
    resp = client.post(
        "/registar",
        data={"email": "exp@exemplo.co.mz", "password": "password123", "display_name": "Exp", "terms_accepted": "on"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    resp = client.get("/explorar")
    assert resp.status_code == 200


def test_landing_page_shown_when_logged_out(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 200
    assert "Boladas-ponto-com" in resp.text
    assert "Do zero ao infinito." in resp.text
    assert "Criar conta grátis" in resp.text
    assert "Feed Social de Negócios" not in resp.text


def test_root_redirects_logged_in_user_to_feed(client):
    client.post(
        "/registar",
        data={
            "email": "landing@exemplo.co.mz",
            "password": "password123",
            "display_name": "Landing",
            "terms_accepted": "on",
        },
        follow_redirects=False,
    )

    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/explorar"


def test_personal_profile_requires_login_and_hides_auth_data_from_other_users(client):
    owner_email = "perfil-privado@exemplo.co.mz"
    client.post(
        "/registar",
        data={
            "email": owner_email,
            "password": "password123",
            "display_name": "Perfil Privado",
            "terms_accepted": "on",
        },
        follow_redirects=False,
    )
    owner = db_module.get_user_by_email(owner_email)
    client.post("/sair", follow_redirects=False)

    resp = client.get(f"/utilizador/{owner['user_id']}", follow_redirects=False)
    assert_login_redirect(resp, f"/utilizador/{owner['user_id']}")

    client.post(
        "/registar",
        data={
            "email": "visitante-perfil@exemplo.co.mz",
            "password": "password123",
            "display_name": "Visitante",
            "terms_accepted": "on",
        },
        follow_redirects=False,
    )
    resp = client.get(f"/utilizador/{owner['user_id']}")
    assert resp.status_code == 200
    assert "Perfil Privado" in resp.text
    assert owner_email not in resp.text
    assert "Provider:" not in resp.text
