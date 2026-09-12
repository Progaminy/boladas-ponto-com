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

    from app.storage import get_backend, post_key

    try:
        # Testa uma chave dentro de posts/, exatamente o prefixo usado pelos
        # anúncios. Isto funciona também quando a Application Key do B2 está
        # corretamente limitada apenas a essa pasta e evita falsos 403 em
        # chaves restritas por prefixo.
        get_backend().head(post_key("__diagnostico__", "ligacao"))
        return Check(
            name="Backblaze B2",
            configured=True,
            ok=True,
            detail=f"Ligado ao bucket «{B2_BUCKET}» com acesso ao prefixo de anúncios.",
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
