from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

REMOVED_MODULES=["ai_status.py","category_classify.py","describe.py","gemini_provider.py","image_compose.py","pipeline.py","provenance.py","verify.py"]

def test_automatic_content_routes_removed():
    paths={r.path for r in app.routes}
    assert "/categoria/sugerir" not in paths
    assert "/descricao/sugerir" not in paths
    assert "/ia/gerar-imagem" not in paths
    assert not any("provenance" in p for p in paths)

def test_removed_modules_absent():
    app_dir=Path(__file__).resolve().parents[1]/"app"
    for name in REMOVED_MODULES: assert not (app_dir/name).exists()

def test_create_page_has_only_manual_publication(tmp_path,monkeypatch):
    from app import db
    monkeypatch.setattr(db,"DB_PATH",tmp_path/"test.db")
    with TestClient(app) as c:
        c.post("/registar",data={"email":"manual@exemplo.co.mz","password":"password123","display_name":"Manual","terms_accepted":"on"},follow_redirects=False)
        r=c.get("/criar")
        assert r.status_code==200
        low=r.text.lower()
        assert "sugerir automaticamente" not in low
        assert "gerar descrição" not in low
        assert 'id="post_photos"' in r.text
