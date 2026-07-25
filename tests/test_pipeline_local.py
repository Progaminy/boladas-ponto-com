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


def _no_providers(monkeypatch):
    """Simula um ambiente sem qualquer provedor de IA configurado."""
    from app import pipeline

    monkeypatch.setattr(pipeline, "ai_provider_order", lambda: [])


def test_generate_image_without_any_provider_fails_honestly(monkeypatch):
    _no_providers(monkeypatch)
    with pytest.raises(GenerationError, match="Nenhum provedor de IA"):
        generate_image(_dummy_input(), _dummy_category())


def test_generate_caption_without_any_provider_fails_honestly(monkeypatch):
    _no_providers(monkeypatch)
    with pytest.raises(GenerationError, match="Nenhum provedor de IA"):
        generate_caption(_dummy_input(), _dummy_category())


def test_image_falls_back_to_gmicloud_when_vertex_fails(monkeypatch):
    """Em modo auto, a falha do Vertex não pode impedir o GMICloud de tentar —
    e o erro final tem de mencionar ambos, sem esconder nenhum."""
    from app import pipeline

    monkeypatch.setattr(pipeline, "ai_provider_order", lambda: ["vertex", "gmicloud"])
    monkeypatch.setattr(pipeline, "AI_PROVIDER", "auto")

    tentativas = []

    def vertex_falha(prompt):
        tentativas.append("vertex")
        raise RuntimeError("sem acesso ao Vertex")

    def gmi_falha(prompt):
        tentativas.append("gmicloud")
        raise RuntimeError("sem saldo GMICloud")

    monkeypatch.setattr(pipeline, "_generate_image_vertex", vertex_falha)
    monkeypatch.setattr(pipeline, "_generate_image_gmi", gmi_falha)

    with pytest.raises(GenerationError) as exc:
        generate_image(_dummy_input(), _dummy_category())

    assert tentativas == ["vertex", "gmicloud"]
    assert "sem acesso ao Vertex" in str(exc.value)
    assert "sem saldo GMICloud" in str(exc.value)


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
