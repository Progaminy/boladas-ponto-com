"""Testa as partes puras/locais do pipeline (prompt building, parsing,
processamento de imagem) sem chamar o GMICloud — não fingimos uma geração
completa sem chaves reais, apenas verificamos a lógica determinística."""

import io
import json

import pytest
from PIL import Image

from app.pipeline import (
    GenerationError,
    _parse_caption_json,
    _to_square_png,
    generate_caption,
    generate_image,
)


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


def test_vertex_caption_runs_inside_genblaze_pipeline(monkeypatch):
    from app import pipeline
    from app.gemini_provider import VertexExpressTextProvider
    from genblaze_core.models.manifest import Manifest

    raw = json.dumps(
        {
            "caption": "Ferramentas prontas para a sua obra.",
            "call_to_action": "Compra já!",
            "hashtags": ["ferragens", "maputo"],
        }
    )
    monkeypatch.setattr(pipeline, "VERTEX_EXPRESS_API_KEY", "test-key")
    monkeypatch.setattr(
        VertexExpressTextProvider,
        "_generate_raw",
        lambda self, step: (
            raw,
            {"google_vertex_express": {"model": step.model}},
            None,
        ),
    )

    result = pipeline._generate_caption_vertex(
        _dummy_input(), pipeline.build_caption_prompt(_dummy_input(), _dummy_category())
    )

    manifest = result.genblaze_manifest
    assert result.caption == "Ferramentas prontas para a sua obra."
    assert result.provider == "google-vertex-express"
    assert result.prompt
    assert manifest["manifest_verified"] is True
    assert manifest["source_asset"]["media_type"] == "application/json"
    assert manifest["native"]["run"]["steps"][0]["modality"] == "text"
    assert manifest["native"]["run"]["steps"][0]["provider"] == "google-vertex-express"
    assert (
        manifest["native"]["run"]["steps"][0]["assets"][0]["url"]
        == "redacted://asset-url"
    )
    assert manifest["native"]["run"]["steps"][0]["provider_payload"] == {}
    assert Manifest.model_validate(manifest["native"]).verify() is True
    assert manifest["native_redacted"] is True


def test_gmicloud_caption_runs_inside_genblaze_pipeline(monkeypatch):
    from app import pipeline
    from app.gemini_provider import GMICloudTextProvider

    raw = json.dumps(
        {
            "caption": "Uma oferta local para si.",
            "call_to_action": "Contacta-nos!",
            "hashtags": ["boladas", "mocambique"],
        }
    )
    monkeypatch.setattr(pipeline, "GMI_API_KEY", "test-key")
    monkeypatch.setattr(
        GMICloudTextProvider,
        "_generate_raw",
        lambda self, step: (
            raw,
            {"gmicloud": {"model": step.model}},
            None,
        ),
    )

    result = pipeline._generate_caption_gmi(
        _dummy_input(), pipeline.build_caption_prompt(_dummy_input(), _dummy_category())
    )

    manifest = result.genblaze_manifest
    assert result.caption == "Uma oferta local para si."
    assert result.provider == "gmicloud"
    assert manifest["manifest_verified"] is True
    assert manifest["native"]["run"]["steps"][0]["modality"] == "text"
    assert manifest["native"]["run"]["steps"][0]["provider"] == "gmicloud"


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
