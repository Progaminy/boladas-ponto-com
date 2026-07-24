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
    image_result: ImageResult,
    caption_result: CaptionResult,
    image_file: UploadedFile,
    caption_file: UploadedFile,
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
        },
        "generation": {
            "prompt": image_result.prompt,
            "models": [
                {"provider": image_result.provider, "model": image_result.model, "role": "image"},
                {"provider": "gmicloud", "model": caption_result.model, "role": "caption"},
            ],
            "parameters": image_result.params,
            "genblaze_used": True,
        },
        "files": {
            "image": {
                "b2_key": image_file.key,
                "content_type": image_file.content_type,
                "size": image_file.size,
                "sha256": image_file.sha256,
            },
            "caption": {
                "b2_key": caption_file.key,
                "content_type": caption_file.content_type,
                "size": caption_file.size,
                "sha256": caption_file.sha256,
            },
        },
        "errors": errors or [],
    }


def build_caption_txt(caption_result: CaptionResult) -> str:
    hashtags_line = " ".join(f"#{h}" for h in caption_result.hashtags)
    return (
        f"{caption_result.caption}\n\n"
        f"{caption_result.call_to_action}\n\n"
        f"{hashtags_line}\n"
    )
