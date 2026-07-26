from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import (
    APP_NAME,
    APP_VERSION,
    SESSION_SECRET_KEY,
    b2_configured,
    gmi_configured,
    vertex_configured,
)
from app.db import init_db
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
    init_db()
    yield


app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY, same_site="lax")
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
        "b2_configured": b2_configured(),
        "vertex_configured": vertex_configured(),
        "gmi_configured": gmi_configured(),
    }


@app.get("/estado", response_class=HTMLResponse)
def status_page(request: Request):
    """Diagnóstico real: exercita mesmo as ligações externas e mostra o erro
    concreto quando algo não funciona."""
    return templates.TemplateResponse(request, "status.html", {"checks": run_all_checks()})
