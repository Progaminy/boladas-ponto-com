"""Orquestra a geração real via Genblaze + GMICloud: uma imagem 1080x1080 e
uma legenda/CTA/hashtags. Nada aqui é simulado — se o Genblaze ou o GMICloud
falharem, a exceção sobe e o post é marcado como `failed` com o erro real."""

import io
import json
import re
from dataclasses import dataclass, field

import httpx
from PIL import Image
from genblaze_core import Modality, Pipeline
from genblaze_gmicloud import GMICloudImageProvider, chat

from app.categories import Category
from app.config import GMI_API_KEY, GMI_CHAT_MODEL, GMI_IMAGE_MODEL, IMAGE_SIZE_PX
from app.models import PostInput


class GenerationError(RuntimeError):
    pass


@dataclass
class ImageResult:
    bytes_: bytes
    content_type: str
    provider: str
    model: str
    prompt: str
    params: dict
    source_url: str


@dataclass
class CaptionResult:
    caption: str
    call_to_action: str
    hashtags: list[str] = field(default_factory=list)
    model: str = ""
    raw_text: str = ""


def build_image_prompt(data: PostInput, category: Category) -> str:
    parts = [
        f"Social media post image for a Mozambican small business ({category.label}).",
        f"Theme: {data.theme}.",
        f"Business/product: {data.business}.",
        f"Visual style: {category.image_style_hint}.",
        f"Tone: {data.tone}.",
    ]
    if data.color_reference:
        parts.append(f"Color reference: {data.color_reference}.")
    parts.append("Square composition, no embedded text, no watermark, high quality, 1:1.")
    return " ".join(parts)


def generate_image(data: PostInput, category: Category) -> ImageResult:
    if not GMI_API_KEY:
        raise GenerationError("GMI_API_KEY não configurada — não é possível gerar imagem real.")

    prompt = build_image_prompt(data, category)
    provider = GMICloudImageProvider()
    params = {"aspect_ratio": "1:1"}

    result = (
        Pipeline("boladas-post-image")
        .step(
            provider,
            model=GMI_IMAGE_MODEL,
            prompt=prompt,
            modality=Modality.IMAGE,
            **params,
        )
        .run(timeout=180, max_retries=1)
    )
    run, manifest = result

    step = run.steps[0]
    if step.status != "succeeded" or not step.assets:
        raise GenerationError(
            f"Falha na geração de imagem via GMICloud ({step.error_code}): {step.error}"
        )

    asset = step.assets[0]
    resp = httpx.get(asset.url, timeout=60)
    resp.raise_for_status()
    image_bytes = _to_square_png(resp.content, IMAGE_SIZE_PX)

    return ImageResult(
        bytes_=image_bytes,
        content_type="image/png",
        provider="gmicloud",
        model=step.model,
        prompt=prompt,
        params=params,
        source_url=asset.url,
    )


def _to_square_png(raw: bytes, size: int) -> bytes:
    """Garante a especificação do concurso: PNG quadrado size x size,
    através de center-crop + resize sobre a imagem realmente devolvida."""
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    w, h = img.size
    side = min(w, h)
    left, top = (w - side) // 2, (h - side) // 2
    img = img.crop((left, top, left + side, top + side)).resize((size, size), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


_HASHTAG_RE = re.compile(r"^#?[\wÀ-ÿ]+$")


def build_caption_prompt(data: PostInput, category: Category) -> str:
    business_line = data.brand_name or data.business
    price_line = f"Preço: {data.price_mt} MT. " if data.price_mt else ""
    location_line = f"Localização: {data.location}. " if data.location else ""
    return (
        "Escreve conteúdo para um post de rede social em "
        f"{data.language}, tom {data.tone}, para o negócio '{business_line}' "
        f"(categoria: {category.label}). Tema: {data.theme}. "
        f"Público-alvo: {data.target_audience}. Objetivo: {data.objective}. "
        f"{price_line}{location_line}"
        f"Chamada para ação sugerida pelo utilizador: '{data.call_to_action}'. "
        "Responde APENAS com um JSON válido, sem markdown, no formato exato: "
        '{"caption": "...", "call_to_action": "...", "hashtags": ["...", "..."]}. '
        "A legenda deve ter 1 a 3 frases curtas. Gera entre 5 e 8 hashtags relevantes, "
        "sem o caractere # incluído."
    )


def _parse_caption_json(text: str) -> dict:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    return json.loads(cleaned)


def generate_caption(data: PostInput, category: Category) -> CaptionResult:
    if not GMI_API_KEY:
        raise GenerationError("GMI_API_KEY não configurada — não é possível gerar legenda real.")

    prompt = build_caption_prompt(data, category)
    resp = chat(GMI_CHAT_MODEL, prompt=prompt, temperature=0.7, max_tokens=400)

    try:
        parsed = _parse_caption_json(resp.text)
        caption = str(parsed["caption"]).strip()
        cta = str(parsed.get("call_to_action") or data.call_to_action).strip()
        hashtags = [
            str(h).lstrip("#").strip() for h in parsed.get("hashtags", []) if str(h).strip()
        ]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise GenerationError(
            f"Resposta do modelo de chat não é um JSON válido: {exc}. Texto: {resp.text[:200]}"
        ) from exc

    if not caption or not hashtags:
        raise GenerationError("Legenda ou hashtags vazias na resposta do modelo de chat.")

    return CaptionResult(
        caption=caption,
        call_to_action=cta,
        hashtags=hashtags,
        model=GMI_CHAT_MODEL,
        raw_text=resp.text,
    )
