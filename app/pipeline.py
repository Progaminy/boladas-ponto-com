"""Geração real de imagem e texto, com Vertex AI Express como principal.

Em `AI_PROVIDER=auto`, Vertex é tentado primeiro; GMICloud continua disponível
como fallback. A imagem passa sempre pelo Pipeline do Genblaze, inclusive no
Vertex, mantendo o manifesto de proveniência.
"""

import io
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx
from PIL import Image
from genblaze_core import Modality, Pipeline
from genblaze_gmicloud import GMICloudImageProvider, chat

from app.categories import Category
from app.config import (
    AI_PROVIDER,
    GEMINI_CHAT_MODEL,
    GEMINI_IMAGE_MODEL,
    GMI_API_KEY,
    GMI_CHAT_MODEL,
    GMI_IMAGE_MODEL,
    IMAGE_SIZE_PX,
    VERTEX_EXPRESS_API_KEY,
    ai_provider_order,
)
from app.formatting import format_price_mt
from app.gemini_provider import (
    GeminiError,
    VertexExpressImageProvider,
    generate_json,
)
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
    genblaze_manifest: dict = field(default_factory=dict)


@dataclass
class CaptionResult:
    caption: str
    call_to_action: str
    hashtags: list[str] = field(default_factory=list)
    provider: str = ""
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
    parts.append(
        "Square composition, no embedded text, no watermark, high quality, 1:1."
    )
    return " ".join(parts)


def _asset_bytes(url: str) -> bytes:
    """O Vertex escreve a imagem para disco (file://), o GMICloud devolve uma
    URL http — ambos os casos têm de funcionar."""
    parsed = urlparse(url)
    if parsed.scheme == "file":
        return Path(unquote(parsed.path)).read_bytes()
    response = httpx.get(url, timeout=60)
    response.raise_for_status()
    return response.content


def _genblaze_manifest(run, manifest, step, asset) -> dict:
    return {
        "run_id": run.run_id,
        "schema_version": manifest.schema_version,
        "canonical_hash": manifest.canonical_hash,
        "manifest_verified": manifest.verify(),
        "step_status": step.status,
        "step_id": step.step_id,
        "retries": step.retries,
        "cost_usd": step.cost_usd,
        "started_at": step.started_at.isoformat() if step.started_at else None,
        "completed_at": step.completed_at.isoformat() if step.completed_at else None,
        "source_asset": {
            "asset_id": asset.asset_id,
            "media_type": asset.media_type,
            "width": asset.width,
            "height": asset.height,
            "sha256": asset.sha256,
        },
    }


def _run_image_pipeline(
    *,
    provider,
    provider_name: str,
    model: str,
    prompt: str,
    params: dict,
) -> ImageResult:
    run, manifest = (
        Pipeline("boladas-post-image")
        .step(
            provider,
            model=model,
            prompt=prompt,
            modality=Modality.IMAGE,
            **params,
        )
        .run(timeout=180, max_retries=1, raise_on_failure=False)
    )

    step = run.steps[0]
    if step.status != "succeeded" or not step.assets:
        raise GenerationError(
            f"Falha na geração de imagem via {provider_name} "
            f"({step.error_code}): {step.error}"
        )

    asset = step.assets[0]
    raw = _asset_bytes(asset.url)
    image_bytes = _to_square_png(raw, IMAGE_SIZE_PX)

    return ImageResult(
        bytes_=image_bytes,
        content_type="image/png",
        provider=provider_name,
        model=step.model,
        prompt=prompt,
        params=params,
        source_url=asset.url,
        genblaze_manifest=_genblaze_manifest(run, manifest, step, asset),
    )


def _generate_image_vertex(prompt: str) -> ImageResult:
    if not VERTEX_EXPRESS_API_KEY:
        raise GenerationError("VERTEX_EXPRESS_API_KEY não configurada.")
    return _run_image_pipeline(
        provider=VertexExpressImageProvider(),
        provider_name="google-vertex-express",
        model=GEMINI_IMAGE_MODEL,
        prompt=prompt,
        params={},
    )


def _generate_image_gmi(prompt: str) -> ImageResult:
    if not GMI_API_KEY:
        raise GenerationError("GMI_API_KEY não configurada.")
    return _run_image_pipeline(
        provider=GMICloudImageProvider(),
        provider_name="gmicloud",
        model=GMI_IMAGE_MODEL,
        prompt=prompt,
        params={"aspect_ratio": "1:1"},
    )


def generate_image(data: PostInput, category: Category) -> ImageResult:
    providers = ai_provider_order()
    if not providers:
        raise GenerationError(
            "Nenhum provedor de IA configurado. Define "
            "VERTEX_EXPRESS_API_KEY ou GMI_API_KEY."
        )

    prompt = build_image_prompt(data, category)
    errors: list[str] = []
    for provider_name in providers:
        try:
            if provider_name == "vertex":
                return _generate_image_vertex(prompt)
            return _generate_image_gmi(prompt)
        except Exception as exc:
            errors.append(f"{provider_name}: {exc}")
            if AI_PROVIDER != "auto":
                break

    # Todos falharam: o erro reportado inclui a razão real de cada provedor,
    # em vez de uma mensagem genérica.
    raise GenerationError(
        "Todos os provedores de imagem configurados falharam. " + " | ".join(errors)
    )


def _to_square_png(raw: bytes, size: int) -> bytes:
    """Garante a especificação do concurso: PNG quadrado size x size,
    através de center-crop + resize sobre a imagem realmente devolvida."""
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    w, h = img.size
    side = min(w, h)
    left, top = (w - side) // 2, (h - side) // 2
    img = img.crop((left, top, left + side, top + side)).resize(
        (size, size), Image.LANCZOS
    )
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


_HASHTAG_RE = re.compile(r"^#?[\wÀ-ÿ]+$")


def build_caption_prompt(data: PostInput, category: Category) -> str:
    business_line = data.brand_name or data.business
    # sem casas decimais quando o preço é inteiro: "850 MT", não "850.0 MT"
    price_line = f"Preço: {format_price_mt(data.price_mt)}. " if data.price_mt else ""
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
        "A legenda deve ter 1 a 3 frases curtas. Gera entre 5 e 8 hashtags "
        "relevantes, sem o caractere # incluído."
    )


def _parse_caption_json(text: str) -> dict:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    return json.loads(cleaned)


def _caption_result(
    parsed: dict,
    raw_text: str,
    data: PostInput,
    *,
    provider: str,
    model: str,
) -> CaptionResult:
    try:
        caption = str(parsed["caption"]).strip()
        cta = str(parsed.get("call_to_action") or data.call_to_action).strip()
        hashtags = [
            str(h).lstrip("#").strip()
            for h in parsed.get("hashtags", [])
            if str(h).strip()
        ]
    except (KeyError, TypeError) as exc:
        raise GenerationError(
            f"Resposta do modelo não tem o formato esperado: {exc}."
        ) from exc

    hashtags = [h for h in hashtags if _HASHTAG_RE.match(h)]
    if not caption or not hashtags:
        raise GenerationError(
            "Legenda ou hashtags vazias/inválidas na resposta do modelo."
        )

    return CaptionResult(
        caption=caption,
        call_to_action=cta,
        hashtags=hashtags,
        provider=provider,
        model=model,
        raw_text=raw_text,
    )


def _generate_caption_vertex(data: PostInput, prompt: str) -> CaptionResult:
    try:
        parsed, raw = generate_json(
            GEMINI_CHAT_MODEL,
            prompt,
            temperature=0.7,
            max_output_tokens=400,
        )
    except GeminiError as exc:
        raise GenerationError(str(exc)) from exc
    return _caption_result(
        parsed,
        raw,
        data,
        provider="google-vertex-express",
        model=GEMINI_CHAT_MODEL,
    )


def _generate_caption_gmi(data: PostInput, prompt: str) -> CaptionResult:
    if not GMI_API_KEY:
        raise GenerationError("GMI_API_KEY não configurada.")
    response = chat(
        GMI_CHAT_MODEL,
        prompt=prompt,
        temperature=0.7,
        max_tokens=400,
    )
    try:
        parsed = _parse_caption_json(response.text)
    except json.JSONDecodeError as exc:
        raise GenerationError(
            "Resposta do modelo de chat não é um JSON válido: "
            f"{exc}. Texto: {response.text[:200]}"
        ) from exc
    return _caption_result(
        parsed,
        response.text,
        data,
        provider="gmicloud",
        model=GMI_CHAT_MODEL,
    )


def generate_caption(data: PostInput, category: Category) -> CaptionResult:
    providers = ai_provider_order()
    if not providers:
        raise GenerationError("Nenhum provedor de IA configurado para gerar a legenda.")

    prompt = build_caption_prompt(data, category)
    errors: list[str] = []
    for provider_name in providers:
        try:
            if provider_name == "vertex":
                return _generate_caption_vertex(data, prompt)
            return _generate_caption_gmi(data, prompt)
        except Exception as exc:
            errors.append(f"{provider_name}: {exc}")
            if AI_PROVIDER != "auto":
                break

    raise GenerationError(
        "Todos os provedores de texto configurados falharam. " + " | ".join(errors)
    )


def build_fallback_caption(data: PostInput, category: Category) -> CaptionResult:
    """Gera uma legenda e hashtags de reserva quando os provedores de IA falharem
    (ex.: quota de API excedida 429). Garante o princípio 'Nunca fingir'
    registando a causa real enquanto permite que o post seja publicado e
    gravado no B2 com sucesso."""
    caption_text = (data.description or "").strip() or f"{data.theme} - {data.business}"
    cta = (data.call_to_action or "").strip() or "Contacta-me já!"
    cat_tag = category.slug.replace("-", "_")
    hashtags = [cat_tag, "boladas", "mocambique", "vendas", "negocios"]

    return CaptionResult(
        caption=caption_text,
        call_to_action=cta,
        hashtags=hashtags,
        provider="fallback_local",
        model="sem_ia_quota_excedida",
        raw_text=caption_text,
    )

