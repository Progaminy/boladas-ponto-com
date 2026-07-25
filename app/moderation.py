"""Moderação de conteúdo em duas camadas:

1. Lista de bloqueio de texto — funciona sempre, sem custo, aplicada ANTES
   de gastar créditos GMICloud a gerar um post. Cobre categorias claramente
   proibidas (armas, drogas ilícitas, tráfico, conteúdo sexual explícito).
2. Classificação por IA (GMICloud chat()) — mais subtil, mas depende de
   créditos GMICloud (o mesmo bloqueio de saldo que afeta a geração). Se
   indisponível, devolve None em vez de fingir que verificou.

Não existe moderação visual automática de fotos/vídeo (não há uma API de
visão verificada disponível). Fotos/vídeo — e texto que passe as duas
camadas acima — ficam cobertos pelo mecanismo de reportar conteúdo em
app/routers/moderation.py, que oculta o post até revisão humana."""

import re

from app.config import GMI_API_KEY, GMI_CHAT_MODEL

BLOCKLIST_TERMS = [
    # armas
    "arma de fogo", "pistola ilegal", "granada", "explosivos", "munição de guerra",
    # drogas ilícitas
    "cocaína", "heroína", "crack", "metanfetamina", "droga ilícita",
    # tráfico / exploração
    "tráfico humano", "escravo", "órgão humano", "órgãos humanos",
    # conteúdo sexual explícito
    "conteúdo sexual explícito", "pornografia",
    # documentos falsificados
    "documento falsificado", "passaporte falso", "bi falso",
]

_PATTERNS = [re.compile(re.escape(term), re.IGNORECASE) for term in BLOCKLIST_TERMS]


def check_text_blocklist(*texts: str) -> list[str]:
    """Devolve os termos proibidos encontrados no texto combinado (lista
    vazia = nada encontrado). Não faz chamadas externas."""
    combined = " ".join(t for t in texts if t)
    matches = []
    for term, pattern in zip(BLOCKLIST_TERMS, _PATTERNS):
        if pattern.search(combined):
            matches.append(term)
    return matches


def ai_moderation_available() -> bool:
    return bool(GMI_API_KEY)


def check_text_with_ai(*texts: str) -> dict | None:
    """Classificação mais subtil via GMICloud chat(). Devolve None (não
    "limpo") quando indisponível ou em erro — nunca finge ter verificado.
    Devolve {"flagged": bool, "reason": str} quando consegue mesmo verificar."""
    if not ai_moderation_available():
        return None

    from genblaze_gmicloud import chat

    combined = " ".join(t for t in texts if t).strip()
    if not combined:
        return {"flagged": False, "reason": ""}

    prompt = (
        "Classifica se o seguinte texto de um anúncio de venda viola políticas de "
        "conteúdo (produtos ilegais, armas, drogas, tráfico, conteúdo sexual explícito, "
        "fraude/burla evidente, discurso de ódio). Responde APENAS com JSON: "
        '{"flagged": true/false, "reason": "..."}.\n\nTexto: ' + combined[:2000]
    )
    try:
        resp = chat(GMI_CHAT_MODEL, prompt=prompt, temperature=0, max_tokens=150)
        import json

        cleaned = re.sub(r"^```(?:json)?|```$", "", resp.text.strip()).strip()
        data = json.loads(cleaned)
        return {"flagged": bool(data.get("flagged")), "reason": str(data.get("reason", ""))}
    except Exception:
        return None
