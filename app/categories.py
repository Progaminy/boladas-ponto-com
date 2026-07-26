"""Registo de categorias de negócio: cada uma tem uma paleta de cores para a
UI (cartões de resultado/histórico) e uma dica de estilo visual injetada no
prompt de geração de imagem, para que o post pareça pertencer à categoria.

Categorias fora desta lista não são bloqueadas — get_category() devolve um
estilo neutro por omissão, preservando o texto que o utilizador escreveu
como rótulo (ver "categoria personalizada" no formulário)."""

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
            accent="#C2410C",
            accent_dark="#7C2D12",
            image_style_hint=(
                "industrial hardware-store aesthetic, warm burnt-orange and brown tones, "
                "bold rugged typography feel, construction materials context"
            ),
        ),
        Category(
            slug="eletricidade",
            label="Eletricidade & Iluminação",
            accent="#F97316",
            accent_dark="#C2410C",
            image_style_hint="electrical/lighting store aesthetic, vivid orange tones, clean technical look",
        ),
        Category(
            slug="mecanica_automovel",
            label="Mecânica & Automóvel",
            accent="#1E3A8A",
            accent_dark="#0F172A",
            image_style_hint="automotive workshop aesthetic, dark navy and black tones, metallic highlights",
        ),
        Category(
            slug="farmacia_saude",
            label="Farmácia & Saúde",
            accent="#FFFFFF",
            accent_dark="#E5E7EB",
            image_style_hint="clean clinical pharmacy look, white and soft blue tones, crisp and trustworthy",
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
            slug="padaria_pastelaria",
            label="Padaria & Pastelaria",
            accent="#D4A017",
            accent_dark="#92400E",
            image_style_hint="warm bakery aesthetic, golden cream and brown tones, soft appetizing light",
        ),
        Category(
            slug="bebidas_bar",
            label="Bebidas & Bar",
            accent="#7C2D92",
            accent_dark="#4C1D4E",
            image_style_hint="moody bar aesthetic, deep purple and wine tones, dramatic lighting",
        ),
        Category(
            slug="moda_vestuario",
            label="Moda & Vestuário",
            accent="#D6336C",
            accent_dark="#A61E4D",
            image_style_hint="elegant editorial fashion look, soft pastel and magenta tones",
        ),
        Category(
            slug="beleza_cosmeticos",
            label="Beleza & Cosméticos",
            accent="#EC4899",
            accent_dark="#9D174D",
            image_style_hint="glamorous beauty-salon look, soft pink and gold tones",
        ),
        Category(
            slug="eletronica_tecnologia",
            label="Eletrónica & Tecnologia",
            accent="#2563EB",
            accent_dark="#1E40AF",
            image_style_hint="clean modern tech aesthetic, cool blue tones, sharp minimal composition",
        ),
        Category(
            slug="informatica_reparacao",
            label="Informática & Reparação",
            accent="#0891B2",
            accent_dark="#155E75",
            image_style_hint="tech-repair shop aesthetic, cyan and dark blue tones, precise clean look",
        ),
        Category(
            slug="telecomunicacoes",
            label="Telecomunicações",
            accent="#4338CA",
            accent_dark="#312E81",
            image_style_hint="modern telecom aesthetic, indigo and blue tones, connectivity feel",
        ),
        Category(
            slug="servicos",
            label="Serviços Gerais",
            accent="#0EA5A0",
            accent_dark="#0B7A76",
            image_style_hint="professional trustworthy look, teal and neutral tones",
        ),
        Category(
            slug="limpeza_domestico",
            label="Limpeza & Serviços Domésticos",
            accent="#38BDF8",
            accent_dark="#0369A1",
            image_style_hint="fresh clean-home aesthetic, light cyan and white tones",
        ),
        Category(
            slug="imobiliario",
            label="Imobiliário",
            accent="#15803D",
            accent_dark="#166534",
            image_style_hint="clean architectural photography style, green and neutral tones",
        ),
        Category(
            slug="moveis_decoracao",
            label="Móveis & Decoração",
            accent="#A16207",
            accent_dark="#713F12",
            image_style_hint="warm interior-design aesthetic, wood-tone browns and beige",
        ),
        Category(
            slug="transporte",
            label="Transporte & Logística",
            accent="#374151",
            accent_dark="#111827",
            image_style_hint="dynamic automotive/logistics look, dark neutral tones with bold highlights",
        ),
        Category(
            slug="agricultura",
            label="Agricultura & Pecuária",
            accent="#65A30D",
            accent_dark="#3F6212",
            image_style_hint="natural outdoor farm aesthetic, earthy green and brown tones",
        ),
        Category(
            slug="educacao",
            label="Educação & Explicações",
            accent="#4F46E5",
            accent_dark="#3730A3",
            image_style_hint="clean academic aesthetic, indigo and white tones, focused and clear",
        ),
        Category(
            slug="eventos_festas",
            label="Eventos & Festas",
            accent="#DB2777",
            accent_dark="#9D174D",
            image_style_hint="festive celebratory aesthetic, vibrant pink and gold tones",
        ),
        Category(
            slug="fotografia_video",
            label="Fotografia & Vídeo",
            accent="#171717",
            accent_dark="#000000",
            image_style_hint="cinematic aesthetic, black and gold tones, dramatic contrast",
        ),
        Category(
            slug="artesanato",
            label="Artesanato",
            accent="#B45309",
            accent_dark="#78350F",
            image_style_hint="handcrafted warm aesthetic, terracotta and earthy tones",
        ),
        Category(
            slug="advocacia_juridico",
            label="Advocacia & Serviços Jurídicos",
            accent="#1E3A5F",
            accent_dark="#0F2942",
            image_style_hint="formal professional aesthetic, deep navy tones, serious and trustworthy",
        ),
        Category(
            slug="contabilidade_financas",
            label="Contabilidade & Finanças",
            accent="#065F46",
            accent_dark="#064E3B",
            image_style_hint="professional finance aesthetic, dark green and gold tones",
        ),
        Category(
            slug="turismo_viagens",
            label="Turismo & Viagens",
            accent="#0D9488",
            accent_dark="#115E59",
            image_style_hint="inviting travel aesthetic, turquoise and warm sand tones",
        ),
        Category(
            slug="papelaria_escolar",
            label="Papelaria & Material Escolar",
            accent="#3B82F6",
            accent_dark="#1D4ED8",
            image_style_hint="bright cheerful stationery aesthetic, blue and yellow tones",
        ),
        Category(
            slug="seguranca",
            label="Segurança",
            accent="#7F1D1D",
            accent_dark="#450A0A",
            image_style_hint="serious security aesthetic, dark red and charcoal tones",
        ),
        Category(
            slug="saude",
            label="Saúde",
            accent="#0284C7",
            accent_dark="#075985",
            image_style_hint="clean clinical look, calm blue and white tones",
        ),
        Category(
            slug="venda_informal",
            label="Venda Pessoal / Mercado Informal",
            accent="#6B7280",
            accent_dark="#374151",
            image_style_hint="informal personal sales marketplace style, friendly approachable product photography",
        ),
        Category(
            slug="outro",
            label="Outra",
            accent="#7C3AED",
            accent_dark="#5B21B6",
            image_style_hint="clean neutral commercial aesthetic",
        ),
    ]
}


def get_category(slug: str | None) -> Category:
    """Devolve o estilo da categoria. Categorias que não existem na lista
    (ex.: texto personalizado escrito pelo utilizador) não são bloqueadas —
    devolvem o estilo neutro por omissão, preservando o texto original como
    rótulo em vez de o substituir por "Outra"."""
    if not slug:
        return CATEGORIES["outro"]
    if slug in CATEGORIES:
        return CATEGORIES[slug]
    fallback = CATEGORIES["outro"]
    return Category(
        slug=slug, label=slug.strip(), accent=fallback.accent,
        accent_dark=fallback.accent_dark, image_style_hint=fallback.image_style_hint,
    )


def list_categories() -> list[Category]:
    return [c for c in CATEGORIES.values() if c.slug not in ("outro", "venda_informal")]
