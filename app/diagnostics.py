"""Diagnóstico real das dependências externas.

A diferença face a um simples `if os.environ.get(...)`: aqui as ligações são
mesmo exercitadas. Ter uma chave configurada não significa que ela funcione —
pode estar errada, expirada ou sem saldo. Esta página diz qual dos casos é,
com a mensagem real do serviço.

As verificações usadas são operações de leitura baratas (consultar um modelo,
listar o catálogo, consultar um objeto), nunca gerações que gastem créditos."""

from dataclasses import dataclass

from app.config import (
    B2_BUCKET,
    GEMINI_CHAT_MODEL,
    GEMINI_IMAGE_MODEL,
    GMI_CHAT_MODEL,
    GMI_IMAGE_MODEL,
    b2_configured,
    gmi_configured,
    vertex_configured,
)
from app.gemini_provider import get_vertex_client


@dataclass
class Check:
    name: str
    configured: bool
    ok: bool
    detail: str

    @property
    def state(self) -> str:
        if not self.configured:
            return "not_configured"
        return "ok" if self.ok else "failing"


def check_b2() -> Check:
    if not b2_configured():
        return Check(
            name="Backblaze B2",
            configured=False,
            ok=False,
            detail="B2_KEY_ID / B2_APP_KEY / B2_BUCKET não estão definidos no ambiente.",
        )

    from app.storage import get_backend

    try:
        # head() num objeto que quase de certeza não existe: confirma
        # autenticação e acesso ao bucket sem escrever nada.
        get_backend().head("__diagnostico_de_ligacao__")
        return Check(
            name="Backblaze B2",
            configured=True,
            ok=True,
            detail=f"Ligado ao bucket «{B2_BUCKET}». Leitura e escrita disponíveis.",
        )
    except Exception as exc:
        return Check(
            name="Backblaze B2",
            configured=True,
            ok=False,
            detail=f"Credenciais presentes mas a ligação falhou: {exc}",
        )


_GEMINI_NAME = "Gemini (Google)"


def check_vertex_express() -> Check:
    if not vertex_configured():
        return Check(
            name=_GEMINI_NAME,
            configured=False,
            ok=False,
            detail="VERTEX_EXPRESS_API_KEY não está definida no ambiente.",
        )

    try:
        # models.list() é uma leitura barata que funciona com chave de API.
        # (models.get() não serve aqui: é uma API administrativa que exige
        # OAuth e devolvia 401 mesmo com uma chave perfeitamente válida.)
        available = {m.name.replace("models/", "") for m in get_vertex_client().models.list()}
    except Exception as exc:
        return Check(
            name=_GEMINI_NAME,
            configured=True,
            ok=False,
            detail=f"Credencial presente, mas o acesso real falhou: {exc}",
        )

    em_falta = [
        m for m in (GEMINI_CHAT_MODEL, GEMINI_IMAGE_MODEL) if m not in available
    ]
    if em_falta:
        return Check(
            name=_GEMINI_NAME,
            configured=True,
            ok=False,
            detail=(
                f"Chave aceite ({len(available)} modelos), mas os modelos "
                f"configurados não estão disponíveis: {', '.join(em_falta)}."
            ),
        )

    return Check(
        name=_GEMINI_NAME,
        configured=True,
        ok=True,
        detail=(
            f"Chave aceite, {len(available)} modelos acessíveis, incluindo "
            f"{GEMINI_CHAT_MODEL} (texto/visão) e {GEMINI_IMAGE_MODEL} (imagem). "
            "Nota: estar listado não garante quota — o plano gratuito do Gemini "
            "tem limite zero para geração de imagem."
        ),
    )


def check_gmicloud() -> Check:
    if not gmi_configured():
        return Check(
            name="GMICloud (fallback)",
            configured=False,
            ok=False,
            detail="GMI_API_KEY não está definida no ambiente.",
        )

    import httpx

    from app.config import GMI_API_KEY

    try:
        response = httpx.get(
            "https://api.gmi-serving.com/v1/models",
            headers={"Authorization": f"Bearer {GMI_API_KEY}"},
            timeout=15,
        )
    except Exception as exc:
        return Check(
            "GMICloud (fallback)", True, False,
            f"Não foi possível contactar o GMICloud: {exc}",
        )

    if response.status_code == 401:
        return Check(
            "GMICloud (fallback)", True, False, "Chave rejeitada (401 não autorizado)."
        )
    if response.status_code != 200:
        return Check(
            "GMICloud (fallback)", True, False,
            f"Resposta inesperada do catálogo ({response.status_code}).",
        )

    ids = {m.get("id") for m in response.json().get("data", [])}
    missing = [
        model
        for model in (GMI_IMAGE_MODEL, GMI_CHAT_MODEL)
        if model not in ids and "/" in model
    ]
    if missing:
        return Check(
            "GMICloud (fallback)", True, False,
            "Chave válida, mas faltam modelos configurados: " + ", ".join(missing),
        )

    return Check(
        name="GMICloud (fallback)",
        configured=True,
        ok=True,
        detail=(
            f"Chave válida, {len(ids)} modelos disponíveis. Nota: uma chave válida "
            "não garante saldo — a geração só é confirmada ao criar um post real."
        ),
    )


def run_all_checks() -> list[Check]:
    return [check_b2(), check_vertex_express(), check_gmicloud()]
