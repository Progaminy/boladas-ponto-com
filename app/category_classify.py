"""Sugestão automática de categoria via GMICloud chat(), para quando o
utilizador não sabe em que categoria o negócio se enquadra. Depende de
saldo GMICloud — devolve None quando indisponível, nunca inventa uma
categoria."""

import json
import re

from app.categories import CATEGORIES
from app.config import GMI_API_KEY, GMI_CHAT_MODEL


def suggest_category(description: str) -> str | None:
    if not GMI_API_KEY or not description.strip():
        return None

    from genblaze_gmicloud import chat

    slugs = [c.slug for c in CATEGORIES.values() if c.slug != "outro"]
    prompt = (
        "Escolhe a categoria mais adequada para este negócio/produto a partir "
        f"EXATAMENTE desta lista de slugs: {slugs}. "
        f"Negócio/produto: {description.strip()[:300]}. "
        'Responde APENAS com JSON: {"slug": "..."}. '
        "Se nenhuma se enquadrar bem, usa \"outro\"."
    )
    try:
        resp = chat(GMI_CHAT_MODEL, prompt=prompt, temperature=0, max_tokens=50)
        cleaned = re.sub(r"^```(?:json)?|```$", "", resp.text.strip()).strip()
        data = json.loads(cleaned)
        slug = str(data.get("slug", "")).strip()
        return slug if slug in CATEGORIES else None
    except Exception:
        return None
