"""Testes para o módulo de moedas internacionais e seleção de prefixo de telefone por país.
"""

from app.currencies import format_contact, format_price, list_currencies, list_phone_prefixes


def test_list_currencies_contains_supported_currencies():
    curr = list_currencies()
    codes = {c["code"] for c in curr}
    assert "MZN" in codes
    assert "USD" in codes
    assert "EUR" in codes
    assert "ZAR" in codes
    assert "AOA" in codes
    assert "BRL" in codes
    assert "GBP" in codes


def test_list_phone_prefixes_contains_mozambique_and_international():
    prefixes = list_phone_prefixes()
    codes = {p["code"] for p in prefixes}
    assert "+258" in codes
    assert "+244" in codes
    assert "+351" in codes
    assert "+27" in codes
    assert "+55" in codes


def test_format_price_for_different_currencies():
    assert "1 500" in format_price(1500, "MZN") and "MT" in format_price(1500, "MZN")
    assert format_price(150.5, "USD") == "$150.50"
    assert "200" in format_price(200, "EUR") and "€" in format_price(200, "EUR")
    assert "3 500" in format_price(3500, "ZAR") and "R" in format_price(3500, "ZAR")
    assert "50 000" in format_price(50000, "AOA") and "Kz" in format_price(50000, "AOA")
    assert "120.75" in format_price(120.75, "BRL") and "R$" in format_price(120.75, "BRL")
    assert "90" in format_price(90, "GBP") and "£" in format_price(90, "GBP")


def test_format_contact_prefixes():
    assert format_contact("+258", "841234567") == "+258 841234567"
    assert format_contact("+244", "923456789") == "+244 923456789"
    assert format_contact(None, "+351912345678") == "+351912345678"
    assert format_contact("+258", "+258841234567") == "+258841234567"
