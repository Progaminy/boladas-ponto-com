"""Sobrepõe texto comercial determinístico (nome do negócio, preço, chamada
para ação) sobre a imagem gerada pela IA. A IA gera a imagem sem texto (texto
gerado por modelos de imagem costuma sair deformado); o texto real do anúncio
é desenhado aqui, de forma determinística, para o post ficar pronto a
publicar."""

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.categories import Category
from app.currencies import format_price
from app.formatting import format_price_mt

_FONTS_DIR = Path(__file__).resolve().parent / "static" / "fonts"
_BOLD_FONT_PATH = _FONTS_DIR / "DejaVuSans-Bold.ttf"
_REGULAR_FONT_PATH = _FONTS_DIR / "DejaVuSans.ttf"

_MAX_NAME_LEN = 60
_MAX_CTA_LEN = 80


def _load_font(path: Path, size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        return ImageFont.load_default()


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )


def _fit_font(
    draw: ImageDraw.ImageDraw, text: str, font_path: Path, max_width: int, start_size: int, min_size: int
) -> ImageFont.ImageFont:
    size = start_size
    while size > min_size:
        font = _load_font(font_path, size)
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            return font
        size -= 2
    return _load_font(font_path, min_size)


def add_business_overlay(
    image_bytes: bytes,
    *,
    category: Category,
    business_name: str,
    price_mt: float | None,
    call_to_action: str,
    currency: str = "MZN",
) -> bytes:
    """Devolve novos bytes PNG com uma faixa inferior (na cor da categoria)
    contendo nome do negócio, preço (se houver) e chamada para ação."""
    base = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    width, height = base.size

    band_height = max(1, int(height * 0.26))
    overlay = Image.new("RGBA", (width, band_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    accent_rgb = _hex_to_rgb(category.accent_dark)
    for y in range(band_height):
        alpha = int(240 * (y / band_height))
        draw.line([(0, y), (width, y)], fill=(*accent_rgb, alpha))

    padding = int(width * 0.05)
    max_text_width = width - 2 * padding

    name_text = business_name.strip()[:_MAX_NAME_LEN]
    name_font = _fit_font(
        draw, name_text, _BOLD_FONT_PATH, max_text_width,
        start_size=max(24, int(width * 0.065)), min_size=16,
    )
    name_y = int(band_height * 0.16)
    draw.text((padding, name_y), name_text, font=name_font, fill=(255, 255, 255, 255))

    cta_text = call_to_action.strip()[:_MAX_CTA_LEN]
    if price_mt:
        cta_text = f"{format_price(price_mt, currency or 'MZN')}  •  {cta_text}"
    cta_font = _fit_font(
        draw, cta_text, _REGULAR_FONT_PATH, max_text_width,
        start_size=max(18, int(width * 0.038)), min_size=13,
    )
    name_bbox = draw.textbbox((0, 0), name_text, font=name_font)
    cta_y = name_y + (name_bbox[3] - name_bbox[1]) + int(band_height * 0.12)
    draw.text((padding, cta_y), cta_text, font=cta_font, fill=(255, 255, 255, 235))

    composed = base.copy()
    composed.alpha_composite(overlay, dest=(0, height - band_height))

    out = io.BytesIO()
    composed.convert("RGB").save(out, format="PNG")
    return out.getvalue()
