"""Formatação partilhada, para que o mesmo valor apareça igual em todo o lado
— na imagem, na legenda gerada e nas páginas."""


def format_price_mt(price_mt: float | None) -> str:
    """Preço em Metical, sem casas decimais e com espaço como separador de
    milhares: 850 → "850 MT", 12500 → "12 500 MT"."""
    if price_mt is None:
        return ""
    return f"{price_mt:,.0f} MT".replace(",", " ")
