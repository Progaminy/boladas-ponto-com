"""Registo de categorias de negócio: cada uma tem uma paleta de cores para a
UI (cartões de resultado/histórico) e uma dica de estilo visual injetada no
prompt de geração de imagem, para que o post pareça pertencer à categoria."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    slug: str
    label: str
    accent: str
    accent_dark: str
    image_style_hint: str


CATEGORIES: dict[str, Category] = {
    c.slug: c
    for c in [
        Category(
            slug="ferragens_construcao",
            label="Ferragens & Construção",
            accent="#FF6B00",
            accent_dark="#CC5500",
            image_style_hint=(
                "industrial hardware-store aesthetic, warm orange and gold tones, "
                "bold rugged typography feel, construction materials context"
            ),
        ),
        Category(
            slug="alimentacao",
            label="Alimentação & Restauração",
            accent="#E53E3E",
            accent_dark="#9B2C2C",
            image_style_hint=(
                "appetizing food-photography style, warm inviting lighting, "
                "vibrant red and gold accents"
            ),
        ),
        Category(
            slug="moda_beleza",
            label="Moda & Beleza",
            accent="#D6336C",
            accent_dark="#A61E4D",
            image_style_hint="elegant editorial fashion look, soft pastel and magenta tones",
        ),
        Category(
            slug="eletronica_tecnologia",
            label="Eletrónica & Tecnologia",
            accent="#2563EB",
            accent_dark="#1E40AF",
            image_style_hint="clean modern tech aesthetic, cool blue tones, sharp minimal composition",
        ),
        Category(
            slug="servicos",
            label="Serviços",
            accent="#0EA5A0",
            accent_dark="#0B7A76",
            image_style_hint="professional trustworthy look, teal and neutral tones",
        ),
        Category(
            slug="imobiliario",
            label="Imobiliário",
            accent="#15803D",
            accent_dark="#166534",
            image_style_hint="clean architectural photography style, green and neutral tones",
        ),
        Category(
            slug="transporte",
            label="Transporte",
            accent="#374151",
            accent_dark="#111827",
            image_style_hint="dynamic automotive look, dark neutral tones with bold highlights",
        ),
        Category(
            slug="agricultura",
            label="Agricultura",
            accent="#65A30D",
            accent_dark="#3F6212",
            image_style_hint="natural outdoor farm aesthetic, earthy green and brown tones",
        ),
        Category(
            slug="saude",
            label="Saúde",
            accent="#0284C7",
            accent_dark="#075985",
            image_style_hint="clean clinical look, calm blue and white tones",
        ),
        Category(
            slug="outro",
            label="Outro",
            accent="#6B7280",
            accent_dark="#4B5563",
            image_style_hint="clean neutral commercial aesthetic",
        ),
    ]
}


def get_category(slug: str) -> Category:
    return CATEGORIES.get(slug, CATEGORIES["outro"])


def list_categories() -> list[Category]:
    return list(CATEGORIES.values())
