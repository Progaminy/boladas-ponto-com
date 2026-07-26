import json
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.categories import list_categories
from app.config import PLATFORM_CONTACT_NUMBER
from app.currencies import format_price, list_currencies, list_phone_prefixes
from app.ai_status import interpretar_falha_de_imagem
from app.formatting import format_price_mt


def _inject_current_user(request: Request) -> dict:
    from app.auth import get_current_user

    return {"current_user": get_current_user(request)}


templates = Jinja2Templates(
    directory=Path(__file__).resolve().parent / "templates",
    context_processors=[_inject_current_user],
)
templates.env.globals["categories"] = list_categories()
templates.env.globals["currencies"] = list_currencies()
templates.env.globals["phone_prefixes"] = list_phone_prefixes()
templates.env.globals["platform_contact"] = PLATFORM_CONTACT_NUMBER
templates.env.filters["from_json"] = lambda s: json.loads(s) if s else []
templates.env.filters["preco_mt"] = format_price_mt
# transforma o erro cru do provedor num estado legível (normalmente uma espera)
templates.env.filters["estado_ia"] = interpretar_falha_de_imagem
templates.env.filters["format_price"] = lambda price, curr="MZN": format_price(price, curr or "MZN")
