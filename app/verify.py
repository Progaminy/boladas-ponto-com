"""Verificação de proveniência ao vivo.

A `provenance.json` afirma um SHA-256 para cada ficheiro. Isso só vale
alguma coisa se alguém puder confirmar, agora, que o ficheiro realmente
armazenado no Backblaze B2 ainda corresponde a essa afirmação.

Este módulo faz exatamente isso: descarrega os bytes reais do B2,
recalcula o hash e compara. Não lê valores em cache nem confia na base de
dados local — se o B2 estiver inacessível, devolve o erro real em vez de
um "verificado" vazio."""

from dataclasses import dataclass
from datetime import datetime, timezone

from app.storage import get_backend, sha256_hex


@dataclass
class FileVerification:
    name: str
    b2_key: str
    claimed_sha256: str
    actual_sha256: str | None
    size_bytes: int | None
    matches: bool
    error: str | None = None


@dataclass
class VerificationReport:
    post_id: str
    verified_at: str
    files: list[FileVerification]

    @property
    def all_match(self) -> bool:
        return bool(self.files) and all(f.matches for f in self.files)

    @property
    def checked_count(self) -> int:
        return sum(1 for f in self.files if f.actual_sha256 is not None)


def verify_post_files(post_id: str, provenance: dict) -> VerificationReport:
    """Re-descarrega do B2 cada ficheiro declarado no manifesto e compara o
    SHA-256 real com o afirmado. Cada ficheiro é verificado de forma
    independente: a falha de um não impede a verificação dos restantes."""
    files_section = (provenance or {}).get("files") or {}
    results: list[FileVerification] = []

    for name, info in files_section.items():
        if not isinstance(info, dict):
            continue
        b2_key = info.get("b2_key")
        claimed = info.get("sha256")
        if not b2_key or not claimed:
            continue

        try:
            data = get_backend().get(b2_key)
        except Exception as exc:
            results.append(
                FileVerification(
                    name=name, b2_key=b2_key, claimed_sha256=claimed,
                    actual_sha256=None, size_bytes=None, matches=False,
                    error=f"Não foi possível obter do B2: {exc}",
                )
            )
            continue

        actual = sha256_hex(data)
        results.append(
            FileVerification(
                name=name, b2_key=b2_key, claimed_sha256=claimed,
                actual_sha256=actual, size_bytes=len(data), matches=actual == claimed,
            )
        )

    return VerificationReport(
        post_id=post_id,
        verified_at=datetime.now(timezone.utc).isoformat(),
        files=results,
    )
