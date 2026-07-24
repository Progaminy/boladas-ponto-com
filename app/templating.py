import json
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.categories import list_categories
from app.config import PLATFORM_CONTACT_NUMBER


def _inject_current_user(request: Request) -> dict:
    from app.auth import get_current_user

    return {"current_user": get_current_user(request)}


templates = Jinja2Templates(
    directory=Path(__file__).resolve().parent / "templates",
    context_processors=[_inject_current_user],
)
templates.env.globals["categories"] = list_categories()
templates.env.globals["platform_contact"] = PLATFORM_CONTACT_NUMBER
templates.env.filters["from_json"] = lambda s: json.loads(s) if s else []
