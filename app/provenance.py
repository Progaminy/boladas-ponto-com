"""Monta o provenance.json exatamente no schema definido pelas regras do
concurso. Nunca inclui credenciais, tokens ou dados de .env."""

from datetime import datetime, timezone

from app.config import APP_NAME, APP_VERSION
from app.models import PostInput
from app.pipeline import CaptionResult, ImageResult
from app.storage import UploadedFile


def build_provenance(
    *,
    post_id: str,
    status: str,
    post_input: PostInput,
    image_result: ImageResult | None,
    caption_result: CaptionResult,
    image_file: UploadedFile | None,
    caption_file: UploadedFile,
    image_skipped_reason: str | None = None,
    caption_skipped_reason: str | None = None,
    errors: list[str] | None = None,
) -> dict:
    return {
        "post_id": post_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "application": APP_NAME,
        "application_version": APP_VERSION,
        "status": status,
        "user_input": {
            "theme": post_input.theme,
            "business": post_input.business,
            "target_audience": post_input.target_audience,
            "objective": post_input.objective,
            "tone": post_input.tone,
            "language": post_input.language,
            "category": post_input.category,
            "publisher_type": post_input.publisher_type.value,
            "brand_name": post_input.brand_name,
            "price_mt": post_input.price_mt,
            "location": post_input.location,
            "contact": post_input.contact,
            "description": post_input.description,
            "description_source": post_input.description_source,
        },
        "generation": {
            "prompt": image_result.prompt if image_result else None,
            "models": _models_usados(image_result, caption_result),
            "parameters": image_result.params if image_result else {},
            "image_generated": image_result is not None,
            "image_skipped_reason": image_skipped_reason,
            "caption_skipped_reason": caption_skipped_reason,
            "genblaze_used": image_result is not None,
            "genblaze_manifest": image_result.genblaze_manifest if image_result else None,
        },
        "files": _ficheiros(image_file, caption_file),
        "errors": errors or [],
    }


def _models_usados(
    image_result: ImageResult | None, caption_result: CaptionResult
) -> list[dict]:
    modelos = []
    if image_result is not None:
        modelos.append(
            {
                "provider": image_result.provider,
                "model": image_result.model,
                "role": "image",
            }
        )
    # o provedor da legenda vem do resultado real, não fixo: com múltiplos
    # provedores, assumir um deles tornaria o manifesto falso quando o outro
    # fosse usado.
    modelos.append(
        {
            "provider": caption_result.provider,
            "model": caption_result.model,
            "role": "caption",
        }
    )
    return modelos


def _ficheiros(
    image_file: UploadedFile | None, caption_file: UploadedFile
) -> dict:
    """Só declara ficheiros que existem mesmo no B2. Uma entrada de imagem
    vazia levaria a verificação ao vivo a procurar um objeto inexistente."""
    ficheiros = {}
    if image_file is not None:
        ficheiros["image"] = {
            "b2_key": image_file.key,
            "content_type": image_file.content_type,
            "size": image_file.size,
            "sha256": image_file.sha256,
        }
    ficheiros["caption"] = {
        "b2_key": caption_file.key,
        "content_type": caption_file.content_type,
        "size": caption_file.size,
        "sha256": caption_file.sha256,
    }
    return ficheiros


def build_caption_txt(caption_result: CaptionResult) -> str:
    hashtags_line = " ".join(f"#{h}" for h in caption_result.hashtags)
    return (
        f"{caption_result.caption}\n\n"
        f"{caption_result.call_to_action}\n\n"
        f"{hashtags_line}\n"
    )
