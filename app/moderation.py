"""Moderação local baseada em regras explícitas e revisão humana."""

import re

BLOCKLIST_TERMS = [
    "arma de fogo",
    "pistola ilegal",
    "granada",
    "explosivos",
    "munição de guerra",
    "cocaína",
    "heroína",
    "crack",
    "metanfetamina",
    "droga ilícita",
    "tráfico humano",
    "escravo",
    "órgão humano",
    "órgãos humanos",
    "conteúdo sexual explícito",
    "pornografia",
    "documento falsificado",
    "passaporte falso",
    "bi falso",
]

_PATTERNS = [re.compile(re.escape(term), re.IGNORECASE) for term in BLOCKLIST_TERMS]


def check_text_blocklist(*texts: str) -> list[str]:
    """Devolve os termos proibidos encontrados no texto combinado."""
    combined = " ".join(t for t in texts if t)
    return [
        term
        for term, pattern in zip(BLOCKLIST_TERMS, _PATTERNS)
        if pattern.search(combined)
    ]
