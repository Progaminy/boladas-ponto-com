"""Sugestão automática de categoria, para quando o utilizador não sabe em que
categoria o seu negócio se enquadra. Tenta o Vertex primeiro e o GMICloud como
fallback; devolve None quando nenhum responde — nunca inventa uma categoria."""

import json
import re

from app.categories import CATEGORIES
from app.config import (
    AI_PROVIDER,
    GEMINI_CHAT_MODEL,
    GMI_API_KEY,
    GMI_CHAT_MODEL,
    ai_provider_order,
)
from app.gemini_provider import generate_json


def suggest_category(description: str) -> str | None:
    if not description.strip():
        return None

    slugs = [c.slug for c in CATEGORIES.values() if c.slug != "outro"]
    prompt = (
        "Escolhe a categoria mais adequada para este negócio/produto a partir "
        f"EXATAMENTE desta lista de slugs: {slugs}. "
        f"Negócio/produto: {description.strip()[:300]}. "
        'Responde APENAS com JSON: {"slug": "..."}. '
        'Se nenhuma se enquadrar bem, usa "outro".'
    )

    for provider in ai_provider_order():
        try:
            if provider == "vertex":
                data, _ = generate_json(
                    GEMINI_CHAT_MODEL,
                    prompt,
                    temperature=0,
                    max_output_tokens=50,
                )
            else:
                if not GMI_API_KEY:
                    continue
                from genblaze_gmicloud import chat

                response = chat(
                    GMI_CHAT_MODEL,
                    prompt=prompt,
                    temperature=0,
                    max_tokens=50,
                )
                cleaned = re.sub(
                    r"^```(?:json)?|```$", "", response.text.strip()
                ).strip()
                data = json.loads(cleaned)

            slug = str(data.get("slug", "")).strip()
            if slug in CATEGORIES:
                return slug
        except Exception:
            if AI_PROVIDER != "auto":
                return None
    return None
