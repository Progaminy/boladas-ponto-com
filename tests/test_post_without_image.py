"""A imagem gerada por IA é opcional: um anúncio com texto, preço, contacto e
fotos reais do produto continua a ser um anúncio válido. Estes testes fixam
que a ausência de imagem é tratada com honestidade, e não escondida."""

import pytest

from app.categories import get_category
from app.models import PostInput, PublisherType
from app.pipeline import CaptionResult, ImageResult
from app.provenance import build_provenance
from app.storage import UploadedFile


def _post_input(**overrides):
    dados = dict(
        theme="Camisa vintage",
        business="Camisa vintage azul tamanho M",
        category="moda_vestuario",
        publisher_type=PublisherType.INDIVIDUAL,
        target_audience="Todos",
        objective="Vender",
        tone="amigável",
        call_to_action="Contacta-me já",
        contact="871234567",
        description="Camisa azul, tamanho M, usada duas vezes.",
        description_source="ia_foto",
    )
    dados.update(overrides)
    return PostInput(**dados)


def _caption():
    return CaptionResult(
        caption="Uma camisa impecável.",
        call_to_action="Contacta-me já!",
        hashtags=["moda", "maputo"],
        provider="google-vertex-express",
        model="gemini-flash-latest",
    )


def _caption_file():
    return UploadedFile(
        key="posts/x/caption.txt", content_type="text/plain", size=42,
        sha256="abc123", url="https://fake-b2.example/posts/x/caption.txt",
    )


def test_provenance_without_image_declares_no_image_file():
    """Declarar um ficheiro de imagem inexistente levaria a verificação ao
    vivo a procurar um objeto que não está no bucket."""
    doc = build_provenance(
        post_id="x", status="completed", post_input=_post_input(),
        image_result=None, caption_result=_caption(),
        image_file=None, caption_file=_caption_file(),
        image_skipped_reason="sem quota de geração de imagem",
    )

    assert "image" not in doc["files"]
    assert "caption" in doc["files"]


def test_provenance_without_image_is_explicit_about_it():
    doc = build_provenance(
        post_id="x", status="completed", post_input=_post_input(),
        image_result=None, caption_result=_caption(),
        image_file=None, caption_file=_caption_file(),
        image_skipped_reason="429 sem quota",
    )
    g = doc["generation"]

    assert g["image_generated"] is False
    assert "429" in g["image_skipped_reason"]
    # sem etapa de imagem, o Pipeline do Genblaze não chegou a correr
    assert g["genblaze_used"] is False
    # e não pode constar um prompt de uma geração que não aconteceu
    assert g["prompt"] is None
    assert [m["role"] for m in g["models"]] == ["caption"]


def test_provenance_with_image_still_records_genblaze():
    image_result = ImageResult(
        bytes_=b"x", content_type="image/png", provider="google-vertex-express",
        model="gemini-2.5-flash-image", prompt="um prompt", params={},
        source_url="file:///tmp/x.png", genblaze_manifest={"run_id": "r1"},
    )
    image_file = UploadedFile(
        key="posts/x/image.png", content_type="image/png", size=10,
        sha256="deadbeef", url="https://fake-b2.example/posts/x/image.png",
    )

    doc = build_provenance(
        post_id="x", status="completed", post_input=_post_input(),
        image_result=image_result, caption_result=_caption(),
        image_file=image_file, caption_file=_caption_file(),
    )
    g = doc["generation"]

    assert g["image_generated"] is True
    assert g["genblaze_used"] is True
    assert g["genblaze_manifest"]["run_id"] == "r1"
    assert {m["role"] for m in g["models"]} == {"image", "caption"}
    assert doc["files"]["image"]["sha256"] == "deadbeef"


def test_description_and_its_origin_are_recorded():
    """Saber se a descrição foi escrita por uma pessoa ou pela IA faz parte
    da proveniência do que é publicado."""
    doc = build_provenance(
        post_id="x", status="completed", post_input=_post_input(),
        image_result=None, caption_result=_caption(),
        image_file=None, caption_file=_caption_file(),
    )

    assert doc["user_input"]["description"].startswith("Camisa azul")
    assert doc["user_input"]["description_source"] == "ia_foto"


@pytest.mark.parametrize("origem", ["manual", "ia_texto", "ia_foto"])
def test_all_description_sources_are_accepted(origem):
    entrada = _post_input(description_source=origem)
    assert entrada.description_source == origem


def test_post_input_accepts_no_description_at_all():
    entrada = _post_input(description=None, description_source=None)
    assert entrada.description is None
