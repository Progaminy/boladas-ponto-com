"""Testa as partes puras/locais do pipeline (prompt building, parsing,
processamento de imagem) sem chamar o GMICloud — não fingimos uma geração
completa sem chaves reais, apenas verificamos a lógica determinística."""

import io
import json

import pytest
from PIL import Image

from app.pipeline import GenerationError, _parse_caption_json, _to_square_png, generate_caption, generate_image


def test_to_square_png_produces_exact_size():
    src = Image.new("RGB", (1600, 900), color=(255, 0, 0))
    buf = io.BytesIO()
    src.save(buf, format="PNG")

    out_bytes = _to_square_png(buf.getvalue(), 1080)
    out_img = Image.open(io.BytesIO(out_bytes))

    assert out_img.size == (1080, 1080)
    assert out_img.format == "PNG"


def test_parse_caption_json_strips_markdown_fences():
    raw = '```json\n{"caption": "ola", "call_to_action": "vai", "hashtags": ["a", "b"]}\n```'
    parsed = _parse_caption_json(raw)
    assert parsed["caption"] == "ola"
    assert parsed["hashtags"] == ["a", "b"]


def test_parse_caption_json_raises_on_invalid_json():
    with pytest.raises(json.JSONDecodeError):
        _parse_caption_json("isto não é JSON")


def test_generate_image_without_api_key_fails_honestly(monkeypatch):
    from app import pipeline

    monkeypatch.setattr(pipeline, "GMI_API_KEY", None)
    with pytest.raises(GenerationError, match="GMI_API_KEY"):
        generate_image(_dummy_input(), _dummy_category())


def test_generate_caption_without_api_key_fails_honestly(monkeypatch):
    from app import pipeline

    monkeypatch.setattr(pipeline, "GMI_API_KEY", None)
    with pytest.raises(GenerationError, match="GMI_API_KEY"):
        generate_caption(_dummy_input(), _dummy_category())


def _dummy_input():
    from app.models import PostInput, PublisherType

    return PostInput(
        theme="Tema",
        business="Negócio",
        category="outro",
        publisher_type=PublisherType.INDIVIDUAL,
        target_audience="Todos",
        objective="Vender",
        tone="neutro",
        call_to_action="Compra",
        contact="123456",
    )


def _dummy_category():
    from app.categories import get_category

    return get_category("outro")
