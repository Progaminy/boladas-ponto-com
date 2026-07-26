from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app import db
from app.auth import get_current_user
from app.categories import list_categories
from app.templating import templates

router = APIRouter()


@router.get("/comparar", response_class=HTMLResponse)
def compare_prices_page(
    request: Request,
    q: str | None = None,
    cat: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    sort: str = "price_asc",
):
    results = db.compare_prices_and_proximity(
        search_query=q,
        category=cat,
        user_lat=lat,
        user_lon=lon,
        sort_by=sort,
    )
    categories = list_categories()
    return templates.TemplateResponse(
        request,
        "compare.html",
        {
            "results": results,
            "categories": categories,
            "search_query": q or "",
            "selected_cat": cat or "",
            "user_lat": lat,
            "user_lon": lon,
            "sort_by": sort,
            "current_user": get_current_user(request),
        },
    )
