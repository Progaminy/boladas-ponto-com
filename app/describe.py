"""Descrição do produto, por três vias.

O utilizador pode escrever a descrição à mão, pedir à IA a partir de uma
explicação rápida, ou pedir à IA a partir de uma fotografia do produto real.
As duas vias de IA usam o Gemini (texto e visão), que funcionam sem depender
de créditos de geração de imagem.

Quando a IA não consegue responder, estas funções levantam DescriptionError
com a razão real — quem estiver a publicar continua a poder escrever a
descrição à mão."""

from app.config import GEMINI_CHAT_MODEL, GMI_API_KEY, GMI_CHAT_MODEL, ai_provider_order
from app.gemini_provider import GeminiError, generate_json

MAX_DESCRIPTION_CHARS = 600


class DescriptionError(RuntimeError):
    pass


def _prompt_base(idioma: str) -> str:
    return (
        f"Escreve em {idioma} uma descrição comercial curta de um produto ou "
        "serviço à venda, com 2 a 4 frases. Sê concreto e honesto: descreve "
        "apenas o que é dito ou visível, sem inventar marcas, medidas, "
        "garantias, certificações ou estado de conservação que não sejam "
        "evidentes. Não inventes preços. "
        'Responde APENAS com JSON: {"description": "..."}.'
    )


def _extrair(dados: dict) -> str:
    texto = str(dados.get("description", "")).strip()
    if not texto:
        raise DescriptionError("A IA devolveu uma descrição vazia.")
    return texto[:MAX_DESCRIPTION_CHARS]


def describe_from_text(explicacao: str, *, idioma: str = "português") -> str:
    """Gera a descrição a partir de uma explicação informal do vendedor."""
    explicacao = (explicacao or "").strip()
    if not explicacao:
        raise DescriptionError("Escreve primeiro uma explicação do produto.")

    prompt = (
        f"{_prompt_base(idioma)}\n\n"
        f"Explicação de quem vende: {explicacao[:1500]}"
    )

    if "vertex" in ai_provider_order():
        try:
            dados, _ = generate_json(GEMINI_CHAT_MODEL, prompt, temperature=0.6)
            return _extrair(dados)
        except GeminiError as exc:
            erro_vertex = str(exc)
    else:
        erro_vertex = "Gemini não configurado."

    if GMI_API_KEY and "gmicloud" in ai_provider_order():
        try:
            return _extrair(_via_gmicloud(prompt))
        except Exception as exc:
            raise DescriptionError(f"{erro_vertex} | GMICloud: {exc}") from exc

    raise DescriptionError(erro_vertex)


def describe_from_image(
    imagem: bytes, mime_type: str, *, contexto: str = "", idioma: str = "português"
) -> str:
    """Gera a descrição a partir de uma fotografia real do produto.

    Só o Gemini tem visão configurada nesta aplicação; sem ele, esta via não
    está disponível e o utilizador escreve a descrição à mão."""
    if not imagem:
        raise DescriptionError("Nenhuma imagem recebida.")
    if "vertex" not in ai_provider_order():
        raise DescriptionError(
            "A descrição a partir de foto precisa do Gemini configurado "
            "(VERTEX_EXPRESS_API_KEY). Podes escrever a descrição à mão."
        )

    prompt = _prompt_base(idioma) + (
        "\n\nDescreve o produto que aparece nesta fotografia."
    )
    if contexto.strip():
        prompt += f" Contexto dado por quem vende: {contexto.strip()[:400]}"

    try:
        dados, _ = generate_json(
            GEMINI_CHAT_MODEL, prompt, temperature=0.4, media=(imagem, mime_type)
        )
    except GeminiError as exc:
        raise DescriptionError(str(exc)) from exc
    return _extrair(dados)


def _via_gmicloud(prompt: str) -> dict:
    import json
    import re

    from genblaze_gmicloud import chat

    resposta = chat(GMI_CHAT_MODEL, prompt=prompt, temperature=0.6, max_tokens=400)
    limpo = re.sub(r"^```(?:json)?|```$", "", resposta.text.strip()).strip()
    return json.loads(limpo)
