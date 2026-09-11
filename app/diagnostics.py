"""Diagnóstico das dependências externas usadas pelo Boladas."""

from dataclasses import dataclass

from app.config import B2_BUCKET, b2_configured


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
        # Uma consulta a uma chave inexistente é suficiente para confirmar que
        # as credenciais conseguem chegar ao bucket sem escrever dados.
        get_backend().head("__diagnostico_de_ligacao__")
        return Check(
            name="Backblaze B2",
            configured=True,
            ok=True,
            detail=f"Ligado ao bucket «{B2_BUCKET}».",
        )
    except Exception as exc:
        return Check(
            name="Backblaze B2",
            configured=True,
            ok=False,
            detail=f"Credenciais presentes mas a ligação falhou: {exc}",
        )


def run_all_checks() -> list[Check]:
    return [check_b2()]
