"""Diagnóstico real das dependências externas.

A diferença face a um simples `if os.environ.get(...)`: aqui as ligações
são mesmo exercitadas. Ter uma chave configurada não significa que ela
funcione — pode estar errada, expirada ou sem saldo. Esta página diz qual
dos casos é, com a mensagem real do serviço.

As verificações usadas são operações de leitura baratas (listar modelos,
consultar um objeto), nunca gerações que gastem créditos."""

from dataclasses import dataclass

from app.config import (
    B2_BUCKET,
    GMI_CHAT_MODEL,
    GMI_IMAGE_MODEL,
    b2_configured,
    gmi_configured,
)


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


def check_gmicloud() -> Check:
    if not gmi_configured():
        return Check(
            name="GMICloud (Genblaze)",
            configured=False,
            ok=False,
            detail="GMI_API_KEY não está definida no ambiente.",
        )

    import httpx

    from app.config import GMI_API_KEY

    try:
        resp = httpx.get(
            "https://api.gmi-serving.com/v1/models",
            headers={"Authorization": f"Bearer {GMI_API_KEY}"},
            timeout=15,
        )
    except Exception as exc:
        return Check(
            name="GMICloud (Genblaze)",
            configured=True,
            ok=False,
            detail=f"Não foi possível contactar o GMICloud: {exc}",
        )

    if resp.status_code == 401:
        return Check("GMICloud (Genblaze)", True, False, "Chave rejeitada (401 não autorizado).")
    if resp.status_code != 200:
        return Check(
            "GMICloud (Genblaze)", True, False,
            f"Resposta inesperada do catálogo de modelos ({resp.status_code}).",
        )

    ids = {m.get("id") for m in resp.json().get("data", [])}
    missing = [m for m in (GMI_IMAGE_MODEL, GMI_CHAT_MODEL) if m not in ids and "/" in m]
    if missing:
        return Check(
            "GMICloud (Genblaze)", True, False,
            f"Chave válida, mas os modelos configurados não constam do catálogo: {', '.join(missing)}.",
        )

    return Check(
        name="GMICloud (Genblaze)",
        configured=True,
        ok=True,
        detail=(
            f"Chave válida, {len(ids)} modelos disponíveis. Nota: uma chave válida não "
            "garante saldo — a geração só é confirmada ao criar um post real."
        ),
    )


def run_all_checks() -> list[Check]:
    return [check_b2(), check_gmicloud()]
