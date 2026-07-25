"""Moderação honesta em três níveis.

1. Lista local de bloqueio: sempre disponível, sem custo, aplicada antes de
   gastar qualquer crédito de geração.
2. Classificação textual por IA: Vertex primeiro, GMICloud como fallback.
3. Verificação multimodal de foto/vídeo: Gemini no Vertex AI Express.

Quando uma chamada externa falha, estas funções devolvem None. Isso significa
"não verificado", nunca "limpo" — o reporte e a revisão humana continuam a ser
a rede de segurança.
"""

import json
import re

from app.config import (
    AI_PROVIDER,
    GEMINI_CHAT_MODEL,
    GMI_API_KEY,
    GMI_CHAT_MODEL,
    ai_provider_order,
    vertex_configured,
)
from app.gemini_provider import generate_json

BLOCKLIST_TERMS = [
    # armas
    "arma de fogo",
    "pistola ilegal",
    "granada",
    "explosivos",
    "munição de guerra",
    # drogas ilícitas
    "cocaína",
    "heroína",
    "crack",
    "metanfetamina",
    "droga ilícita",
    # tráfico / exploração
    "tráfico humano",
    "escravo",
    "órgão humano",
    "órgãos humanos",
    # conteúdo sexual explícito
    "conteúdo sexual explícito",
    "pornografia",
    # documentos falsificados
    "documento falsificado",
    "passaporte falso",
    "bi falso",
]

_PATTERNS = [re.compile(re.escape(term), re.IGNORECASE) for term in BLOCKLIST_TERMS]

_POLICY = (
    "produtos ilegais, armas, drogas, tráfico/exploração, conteúdo sexual "
    "explícito, fraude ou burla evidente, discurso de ódio, documentos "
    "falsificados e venda de pessoas ou órgãos"
)


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
    return bool(ai_provider_order())


def _normalise_result(data: dict) -> dict:
    return {
        "flagged": bool(data.get("flagged")),
        "reason": str(data.get("reason", "")).strip(),
    }


def check_text_with_ai(*texts: str) -> dict | None:
    """Classificação mais subtil do que a lista de bloqueio. Devolve None
    (não "limpo") quando nenhum provedor conseguiu responder."""
    combined = " ".join(t for t in texts if t).strip()
    if not combined:
        return {"flagged": False, "reason": ""}

    prompt = (
        f"Classifica se este anúncio viola políticas de conteúdo ({_POLICY}). "
        'Responde APENAS com JSON: {"flagged": true/false, "reason": "..."}.\n\n'
        "Texto: " + combined[:3000]
    )

    for provider in ai_provider_order():
        try:
            if provider == "vertex":
                data, _ = generate_json(
                    GEMINI_CHAT_MODEL,
                    prompt,
                    temperature=0,
                    max_output_tokens=150,
                )
            else:
                if not GMI_API_KEY:
                    continue
                from genblaze_gmicloud import chat

                response = chat(
                    GMI_CHAT_MODEL,
                    prompt=prompt,
                    temperature=0,
                    max_tokens=150,
                )
                cleaned = re.sub(
                    r"^```(?:json)?|```$", "", response.text.strip()
                ).strip()
                data = json.loads(cleaned)
            return _normalise_result(data)
        except Exception:
            if AI_PROVIDER != "auto":
                return None
    return None


def check_media_with_ai(data: bytes, mime_type: str) -> dict | None:
    """Verifica conteúdo visual real (fotos e vídeo) com o Gemini.

    None significa que não foi verificado — por exemplo sem chave Vertex, ou
    se a chamada falhar. Nunca devolve "limpo" por omissão."""
    if not vertex_configured() or not data:
        return None

    prompt = (
        "Analisa esta imagem ou vídeo de um anúncio comercial. "
        f"Marca como violação apenas quando houver evidência visual de {_POLICY}. "
        "Não marques produtos comuns apenas por incerteza. "
        'Responde APENAS com JSON: {"flagged": true/false, "reason": "..."}.'
    )
    try:
        result, _ = generate_json(
            GEMINI_CHAT_MODEL,
            prompt,
            temperature=0,
            max_output_tokens=200,
            media=(data, mime_type),
        )
        return _normalise_result(result)
    except Exception:
        return None
