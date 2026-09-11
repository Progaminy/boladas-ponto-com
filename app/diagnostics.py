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
        return Check("Backblaze B2", False, False, "B2_KEY_ID / B2_APP_KEY / B2_BUCKET não estão definidos no ambiente.")
    from app.storage import get_backend
    try:
        get_backend().head("__diagnostico_de_ligacao__")
        return Check("Backblaze B2", True, True, f"Ligado ao bucket «{B2_BUCKET}». O armazenamento de ficheiros está acessível.")
    except Exception as exc:
        return Check("Backblaze B2", True, False, f"Credenciais presentes mas a ligação falhou: {exc}")


def run_all_checks() -> list[Check]:
    return [check_b2()]
