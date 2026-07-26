"""Router para geração e edição de imagens via IA (avatares, logotipos, fotos de capa e produtos)."""

import uuid
from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse

from app import db
from app.auth import get_current_user
from app.categories import get_category
from app.pipeline import GenerationError, _generate_image_gmi, _generate_image_vertex
from app.config import ai_provider_order, AI_PROVIDER
from app.storage import StorageError, upload_and_verify, user_key, business_key

router = APIRouter()


def _generate_ai_image_prompt(item_type: str, style_or_prompt: str, context_name: str = "") -> str:
    parts = [
        f"High quality {item_type} for '{context_name}' in Mozambique.",
        f"Style/details: {style_or_prompt}.",
        "Professional commercial graphic design, clean composition, high resolution."
    ]
    return " ".join(parts)


@router.post("/ia/gerar-imagem")
def generate_ai_asset(
    request: Request,
    asset_type: str = Form(...),  # 'avatar', 'logo', 'cover', 'product'
    prompt_details: str = Form(...),
    context_id: str | None = Form(None),  # business_id ou post_id
):
    user = get_current_user(request)
    if user is None:
        return JSONResponse({"error": "Autenticação necessária."}, status_code=401)

    providers = ai_provider_order()
    if not providers:
        return JSONResponse(
            {"error": "Nenhum provedor de IA configurado no momento. Podes carregar uma foto da tua galeria!"},
            status_code=503,
        )

    full_prompt = _generate_ai_image_prompt(asset_type, prompt_details, user["display_name"])
    image_result = None
    errors = []

    for provider_name in providers:
        try:
            if provider_name == "vertex":
                image_result = _generate_image_vertex(full_prompt)
            else:
                image_result = _generate_image_gmi(full_prompt)
            break
        except Exception as exc:
            errors.append(f"{provider_name}: {exc}")
            if AI_PROVIDER != "auto":
                break

    if image_result is None:
        return JSONResponse(
            {
                "error": (
                    "A geração de imagem via IA está indisponível neste momento "
                    "(quota/créditos excedidos). Podes carregar uma foto da tua galeria!"
                ),
                "details": errors,
            },
            status_code=503,
        )

    # Se a imagem foi gerada com sucesso, guarda no B2 e associa
    filename = f"ai_{asset_type}_{uuid.uuid4().hex[:8]}.png"
    if asset_type in ("avatar", "logo") and context_id:
        key = business_key(context_id, filename)
    else:
        key = user_key(user["user_id"], filename)

    try:
        uploaded = upload_and_verify(key, image_result.bytes_, "image/png")
        return JSONResponse(
            {
                "success": True,
                "url": uploaded.url,
                "b2_key": uploaded.key,
                "asset_type": asset_type,
            }
        )
    except StorageError as exc:
        return JSONResponse({"error": f"Erro ao guardar no B2: {exc}"}, status_code=500)
