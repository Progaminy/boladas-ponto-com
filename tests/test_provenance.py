from app.models import PostInput, PublisherType
from app.pipeline import CaptionResult, ImageResult, build_caption_prompt, build_image_prompt
from app.provenance import build_caption_txt, build_provenance
from app.storage import UploadedFile
from app.categories import get_category


def _sample_input():
    return PostInput(
        theme="Promoção de fim de semana",
        business="Loja de ferragens Manuel",
        category="ferragens_construcao",
        publisher_type=PublisherType.BUSINESS,
        brand_name="Ferragens Manuel",
        target_audience="Donos de obra em Maputo",
        objective="Aumentar vendas",
        tone="amigável",
        language="pt",
        call_to_action="Visita-nos já!",
        price_mt=1500,
        location="Maputo, Malhangalene",
        contact="+258871234567",
    )


def test_build_image_prompt_includes_category_style_hint():
    data = _sample_input()
    category = get_category(data.category)
    prompt = build_image_prompt(data, category)
    assert category.image_style_hint in prompt
    assert data.theme in prompt


def test_build_caption_prompt_requests_json():
    data = _sample_input()
    category = get_category(data.category)
    prompt = build_caption_prompt(data, category)
    assert "JSON" in prompt
    assert data.call_to_action in prompt


def test_provenance_schema_matches_contest_spec():
    data = _sample_input()
    image_result = ImageResult(
        bytes_=b"fake",
        content_type="image/png",
        provider="gmicloud",
        model="seedream-5.0-lite",
        prompt="a prompt",
        params={"aspect_ratio": "1:1"},
        source_url="https://gmi.example/img.png",
    )
    caption_result = CaptionResult(
        caption="Ferramentas de qualidade ao melhor preço.",
        call_to_action="Visita-nos já!",
        hashtags=["ferragens", "maputo", "construcao"],
        model="deepseek-ai/DeepSeek-V3",
        raw_text="{...}",
    )
    image_file = UploadedFile(
        key="posts/x/image.png", content_type="image/png", size=4,
        sha256="deadbeef", url="https://fake-b2.example/posts/x/image.png",
    )
    caption_file = UploadedFile(
        key="posts/x/caption.txt", content_type="text/plain", size=10,
        sha256="cafebabe", url="https://fake-b2.example/posts/x/caption.txt",
    )

    doc = build_provenance(
        post_id="x",
        status="completed",
        post_input=data,
        image_result=image_result,
        caption_result=caption_result,
        image_file=image_file,
        caption_file=caption_file,
    )

    assert doc["post_id"] == "x"
    assert doc["status"] == "completed"
    assert doc["application"] == "Boladas-ponto-com"
    assert doc["user_input"]["theme"] == data.theme
    assert doc["generation"]["genblaze_used"] is True
    assert doc["generation"]["prompt"] == image_result.prompt
    assert doc["files"]["image"]["b2_key"] == "posts/x/image.png"
    assert doc["files"]["image"]["sha256"] == "deadbeef"
    assert doc["files"]["caption"]["b2_key"] == "posts/x/caption.txt"
    assert doc["errors"] == []

    # Nunca deve conter credenciais/segredos.
    dump = str(doc)
    for forbidden in ["B2_APP_KEY", "GMI_API_KEY", "app_key", "api_key", "password"]:
        assert forbidden not in dump


def test_caption_txt_contains_hashtags_with_hash_prefix():
    caption_result = CaptionResult(
        caption="Texto",
        call_to_action="Compra já",
        hashtags=["a", "b"],
        model="m",
        raw_text="",
    )
    txt = build_caption_txt(caption_result)
    assert "#a" in txt and "#b" in txt
    assert "Compra já" in txt
