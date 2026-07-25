from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import APP_NAME, APP_VERSION, SESSION_SECRET_KEY, b2_configured, gmi_configured
from app.db import init_db
from app.routers import (
    auth,
    business,
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

app.include_router(auth.router)
app.include_router(business.router)
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
    return {
        "app": APP_NAME,
        "version": APP_VERSION,
        "b2_configured": b2_configured(),
        "gmi_configured": gmi_configured(),
    }
