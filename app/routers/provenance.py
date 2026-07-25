import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app import db
from app.storage import get_backend
from app.templating import templates
from app.verify import verify_post_files

router = APIRouter()


def _load_provenance(row) -> tuple[dict | None, str | None]:
    """Devolve (manifesto, erro). Nunca inventa um manifesto — se o B2 falhar,
    o erro real sobe para a UI."""
    if not row["provenance_key"]:
        return None, "Este post ainda não tem proveniência armazenada no B2."
    try:
        raw = get_backend().get(row["provenance_key"])
        return json.loads(raw), None
    except Exception as exc:
        return None, f"Não foi possível obter o provenance.json real do B2: {exc}"


@router.get("/posts/{post_id}/provenance", response_class=HTMLResponse)
def provenance_page(request: Request, post_id: str):
    # Público de propósito: a proveniência tem de poder ser verificada por
    # qualquer pessoa (incluindo os jurados) sem precisar de conta.
    row = db.get_post(post_id)
    if row is None:
        return templates.TemplateResponse(
            request, "provenance.html",
            {"post_id": post_id, "post": None, "provenance": None, "fetch_error": "Post não encontrado."},
            status_code=404,
        )

    provenance, fetch_error = _load_provenance(row)
    return templates.TemplateResponse(
        request,
        "provenance.html",
        {"post_id": post_id, "post": row, "provenance": provenance, "fetch_error": fetch_error},
    )


@router.post("/posts/{post_id}/verificar")
def verify_now(post_id: str):
    """Verificação ao vivo: vai buscar os bytes reais ao B2 neste momento e
    recalcula o SHA-256, comparando com o que o manifesto afirma. É isto que
    torna a proveniência auditável em vez de decorativa."""
    row = db.get_post(post_id)
    if row is None:
        return JSONResponse({"error": "Post não encontrado."}, status_code=404)

    provenance, fetch_error = _load_provenance(row)
    if provenance is None:
        return JSONResponse({"error": fetch_error}, status_code=502)

    report = verify_post_files(post_id, provenance)
    if not report.files:
        return JSONResponse(
            {"error": "O manifesto não declara ficheiros verificáveis."}, status_code=422
        )

    return JSONResponse({
        "post_id": report.post_id,
        "verified_at": report.verified_at,
        "all_match": report.all_match,
        "checked_count": report.checked_count,
        "files": [
            {
                "name": f.name,
                "b2_key": f.b2_key,
                "claimed_sha256": f.claimed_sha256,
                "actual_sha256": f.actual_sha256,
                "size_bytes": f.size_bytes,
                "matches": f.matches,
                "error": f.error,
            }
            for f in report.files
        ],
    })
