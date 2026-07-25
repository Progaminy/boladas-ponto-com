"""Teste de integração real (não simulado) contra o GMICloud e o Backblaze B2
verdadeiros. NÃO corre por omissão — exige `RUN_LIVE_INTEGRATION_TESTS=1` e
credenciais reais no ambiente, para nunca gastar créditos GMICloud nem
escrever no bucket de produção sem intenção explícita.

Como correr, depois de haver saldo no GMICloud:

    set -a && source .env && set +a
    RUN_LIVE_INTEGRATION_TESTS=1 pytest -q tests/test_integration_live.py -v -s

Gera uma imagem e legenda reais, sobrepõe o texto, envia os 3 ficheiros para
`posts/<post_id>/` no bucket real, confirma o SHA-256 remoto, e depois apaga
esse post de teste do bucket."""

import json
import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_INTEGRATION_TESTS") != "1",
    reason="Define RUN_LIVE_INTEGRATION_TESTS=1 e credenciais reais para correr este teste.",
)


def test_generate_real_post_end_to_end():
    from app.categories import get_category
    from app.image_compose import add_business_overlay
    from app.models import PostInput, PublisherType
    from app.pipeline import generate_caption, generate_image
    from app.provenance import build_caption_txt, build_provenance
    from app.storage import get_backend, post_key, upload_and_verify

    post_input = PostInput(
        theme="Teste de integração real do Boladas-ponto-com",
        business="Post de teste automatizado",
        category="outro",
        publisher_type=PublisherType.INDIVIDUAL,
        target_audience="Equipa de desenvolvimento",
        objective="Validar o pipeline ponta-a-ponta",
        tone="neutro",
        call_to_action="Isto é um teste",
        contact="000000000",
    )
    category = get_category(post_input.category)
    post_id = f"integration-test-{uuid.uuid4().hex[:12]}"

    image_result = generate_image(post_input, category)
    assert image_result.bytes_
    assert image_result.genblaze_manifest["manifest_verified"] is True
    print(f"\nImagem gerada via {image_result.provider}/{image_result.model}")

    caption_result = generate_caption(post_input, category)
    assert caption_result.caption
    assert caption_result.hashtags
    print(f"Legenda: {caption_result.caption}")
    print(f"Hashtags: {caption_result.hashtags}")

    final_bytes = add_business_overlay(
        image_result.bytes_,
        category=category,
        business_name=post_input.business,
        price_mt=None,
        call_to_action=caption_result.call_to_action,
    )

    try:
        image_file = upload_and_verify(post_key(post_id, "image.png"), final_bytes, "image/png")
        caption_file = upload_and_verify(
            post_key(post_id, "caption.txt"),
            build_caption_txt(caption_result).encode("utf-8"),
            "text/plain",
        )
        provenance_doc = build_provenance(
            post_id=post_id,
            status="completed",
            post_input=post_input,
            image_result=image_result,
            caption_result=caption_result,
            image_file=image_file,
            caption_file=caption_file,
        )
        upload_and_verify(
            post_key(post_id, "provenance.json"),
            json.dumps(provenance_doc, ensure_ascii=False, indent=2).encode("utf-8"),
            "application/json",
        )

        print(f"Post real criado em posts/{post_id}/ — URL: {image_file.url}")
        assert image_file.sha256
        assert image_file.size > 0
    finally:
        get_backend().delete_prefix(f"posts/{post_id}/")
        print(f"Post de teste posts/{post_id}/ removido do bucket.")
