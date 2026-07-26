"""Definições e utilitários de moedas internacionais e prefixos telefónicos por país.
"""

from typing import Any, Dict, List

CURRENCIES: Dict[str, Dict[str, str]] = {
    "MZN": {"code": "MZN", "symbol": "MT", "name": "Metical Moçambicano", "format": "{price} MT"},
    "USD": {"code": "USD", "symbol": "$", "name": "Dólar Americano", "format": "${price}"},
    "EUR": {"code": "EUR", "symbol": "€", "name": "Euro", "format": "€{price}"},
    "ZAR": {"code": "ZAR", "symbol": "R", "name": "Rand Sul-Africano", "format": "R {price}"},
    "AOA": {"code": "AOA", "symbol": "Kz", "name": "Kwanza Angolano", "format": "{price} Kz"},
    "BRL": {"code": "BRL", "symbol": "R$", "name": "Real Brasileiro", "format": "R$ {price}"},
    "GBP": {"code": "GBP", "symbol": "£", "name": "Libra Esterlina", "format": "£{price}"},
}

PHONE_PREFIXES: List[Dict[str, str]] = [
    {"code": "+258", "flag": "🇲🇿", "country": "Moçambique (+258)"},
    {"code": "+244", "flag": "🇦🇴", "country": "Angola (+244)"},
    {"code": "+351", "flag": "🇵🇹", "country": "Portugal (+351)"},
    {"code": "+27", "flag": "🇿🇦", "country": "África do Sul (+27)"},
    {"code": "+55", "flag": "🇧🇷", "country": "Brasil (+55)"},
    {"code": "+1", "flag": "🇺🇸", "country": "EUA / Canadá (+1)"},
    {"code": "+263", "flag": "🇿🇼", "country": "Zimbábue (+263)"},
    {"code": "+260", "flag": "🇿🇲", "country": "Zâmbia (+260)"},
    {"code": "+265", "flag": "🇲🇼", "country": "Maláui (+265)"},
    {"code": "+268", "flag": "🇸🇿", "country": "Eswatini (+268)"},
    {"code": "+255", "flag": "🇹🇿", "country": "Tanzânia (+255)"},
    {"code": "+971", "flag": "🇦🇪", "country": "Emirados Árabes (+971)"},
    {"code": "+44", "flag": "🇬🇧", "country": "Reino Unido (+44)"},
    {"code": "+86", "flag": "🇨🇳", "country": "China (+86)"},
    {"code": "+", "flag": "🌐", "country": "Outro (+...)"},
]


def list_currencies() -> List[Dict[str, str]]:
    return list(CURRENCIES.values())


def list_phone_prefixes() -> List[Dict[str, str]]:
    return PHONE_PREFIXES


def format_price(price: float | int | None, currency_code: str = "MZN") -> str:
    if price is None:
        return ""
    
    # Formatação limpa do número
    if isinstance(price, float) and price.is_integer():
        formatted_num = f"{int(price):,}".replace(",", " ")
    elif isinstance(price, (int, float)):
        formatted_num = f"{price:,.2f}".replace(",", " ")
    else:
        formatted_num = str(price)

    info = CURRENCIES.get(currency_code.upper(), CURRENCIES["MZN"])
    return info["format"].format(price=formatted_num)


def format_contact(prefix: str | None, phone: str) -> str:
    phone = (phone or "").strip()
    if not phone:
        return ""
    if phone.startswith("+"):
        return phone
    prefix = (prefix or "").strip()
    if prefix and prefix != "+":
        return f"{prefix} {phone}"
    return phone
