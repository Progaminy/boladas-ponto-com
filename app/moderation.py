"""Moderação local e revisão humana.

O Boladas não usa geração ou classificação automática externa. A proteção
local bloqueia termos explicitamente proibidos; denúncias e casos ambíguos
seguem para revisão humana pela equipa da plataforma.
"""

import re

BLOCKLIST_TERMS = [
    "arma de fogo", "pistola ilegal", "granada", "explosivos", "munição de guerra",
    "cocaína", "heroína", "crack", "metanfetamina", "droga ilícita",
    "tráfico humano", "escravo", "órgão humano", "órgãos humanos",
    "conteúdo sexual explícito", "pornografia", "documento falsificado",
    "passaporte falso", "bi falso",
]

_PATTERNS = [re.compile(re.escape(term), re.IGNORECASE) for term in BLOCKLIST_TERMS]


def check_text_blocklist(*texts: str) -> list[str]:
    combined = " ".join(t for t in texts if t)
    return [term for term, pattern in zip(BLOCKLIST_TERMS, _PATTERNS) if pattern.search(combined)]
