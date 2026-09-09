from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from app.database_url_override import apply_pooler_host_override

# Supabase's shared pooler has multiple regional shards. Render keeps the
# complete DATABASE_URL secret, while SUPABASE_POOLER_HOST can correct only
# the hostname without exposing or rewriting the database credentials.
apply_pooler_host_override()

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import (
    APP_NAME,
    APP_VERSION,
    SESSION_SECRET_KEY,
    SESSION_COOKIE_SECURE,
    b2_configured,
    gmi_configured,
    vertex_configured,
)
from app.database_backend import database_backend_name, install_database_backend

# Must run before importing app.db: the legacy data-access layer talks to the
# sqlite3 DB-API directly. With DATABASE_URL configured this transparently
# switches those calls to PostgreSQL/Supabase while keeping SQLite for tests
# and local development.
install_database_backend()

from app.db import get_conn, init_db
from app.diagnostics import run_all_checks
from app.templating import templates
from app.routers import (
    ai_edit,
    auth,
    business,
    compare,
    explore,
    history,
    media,
    messages,
    moderation,
    posts,
    profile,
    provenance,
    transactions,
)

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    # SQLite owns its local schema and demo seed lifecycle. PostgreSQL/Supabase
    # is migration-managed instead: a restricted runtime role must never need
    # CREATE/ALTER/DROP privileges merely to start the web service.
    if database_backend_name() == "sqlite":
        init_db()
    else:
        # Read-only smoke test at startup. It does not block the web service,
        # but makes pooler/credential mistakes immediately visible in Render.
        try:
            with get_conn() as conn:
                conn.execute("SELECT 1").fetchone()
                conn.execute("SELECT user_id FROM users LIMIT 1").fetchone()
            print("DATABASE_STARTUP_CHECK=ok", flush=True)
        except Exception as exc:
            print(
                f"DATABASE_STARTUP_CHECK=failed {type(exc).__name__}: {str(exc)[:500]}",
                flush=True,
            )
    provenance.reset_verification_rate_limits()
    yield


app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    same_site="lax",
    https_only=SESSION_COOKIE_SECURE,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

app.include_router(ai_edit.router)
app.include_router(auth.router)
app.include_router(business.router)
app.include_router(compare.router)
app.include_router(explore.router)
app.include_router(messages.router)
app.include_router(media.router)
app.include_router(transactions.router)
app.include_router(moderation.router)
app.include_router(profile.router)
app.include_router(posts.router)
app.include_router(history.router)
app.include_router(provenance.router)


@app.get("/health")
def health() -> dict:
    """Health-check leve (usado pelo Render): não contacta serviços externos,
    para não falhar o deploy por causa de uma dependência de terceiros."""
    return {
        "app": APP_NAME,
        "version": APP_VERSION,
        "database_backend": database_backend_name(),
        "b2_configured": b2_configured(),
        "vertex_configured": vertex_configured(),
        "gmi_configured": gmi_configured(),
    }


@app.get("/health/db")
def database_health():
    """Diagnóstico explícito da ligação ao banco, separado do health check do Render."""
    try:
        with get_conn() as conn:
            conn.execute("SELECT 1").fetchone()
            conn.execute("SELECT user_id FROM users LIMIT 1").fetchone()
        return {"ok": True, "database_backend": database_backend_name()}
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "database_backend": database_backend_name(),
                "error": str(exc)[:500],
            },
        )


@app.get("/estado", response_class=HTMLResponse)
def status_page(request: Request):
    """Diagnóstico real: exercita mesmo as ligações externas e mostra o erro
    concreto quando algo não funciona."""
    return templates.TemplateResponse(request, "status.html", {"checks": run_all_checks()})
