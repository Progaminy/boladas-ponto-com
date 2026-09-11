from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from app.database_url_override import apply_pooler_host_override

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
)
from app.database_backend import database_backend_name, install_database_backend

install_database_backend()

from app.db import get_conn, init_db
from app.diagnostics import run_all_checks
from app.templating import templates
from app.routers import (
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
    transactions,
)

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    if database_backend_name() == "sqlite":
        init_db()
    else:
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
    yield


app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    same_site="lax",
    https_only=SESSION_COOKIE_SECURE,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

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


@app.get("/health")
def health() -> dict:
    return {
        "app": APP_NAME,
        "version": APP_VERSION,
        "database_backend": database_backend_name(),
        "b2_configured": b2_configured(),
    }


@app.get("/health/db")
def database_health():
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
    return templates.TemplateResponse(request, "status.html", {"checks": run_all_checks()})
