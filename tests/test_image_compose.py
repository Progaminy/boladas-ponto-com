import io

from PIL import Image

from app.categories import get_category
from app.image_compose import add_business_overlay


def _sample_png(size=(1080, 1080), color=(30, 30, 30)) -> bytes:
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_overlay_preserves_dimensions_and_is_valid_png():
    category = get_category("alimentacao")
    out = add_business_overlay(
        _sample_png(),
        category=category,
        business_name="Confeitaria da Maria",
        price_mt=800,
        call_to_action="Encomenda já!",
    )
    img = Image.open(io.BytesIO(out))
    assert img.format == "PNG"
    assert img.size == (1080, 1080)


def test_overlay_handles_long_business_name_without_crashing():
    category = get_category("outro")
    long_name = "Loja de Ferragens e Materiais de Construção Lendária de Maputo " * 2
    out = add_business_overlay(
        _sample_png(),
        category=category,
        business_name=long_name,
        price_mt=None,
        call_to_action="Visita-nos já! " * 5,
    )
    img = Image.open(io.BytesIO(out))
    assert img.size == (1080, 1080)


def test_overlay_without_price_still_shows_cta():
    category = get_category("servicos")
    out = add_business_overlay(
        _sample_png(size=(600, 600)),
        category=category,
        business_name="Serviços Rápidos",
        price_mt=None,
        call_to_action="Contacta-nos",
    )
    img = Image.open(io.BytesIO(out))
    assert img.size == (600, 600)
