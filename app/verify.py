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

import re

from app.storage import get_backend, sha256_hex


# A verificação é pública, mas não pode ser usada como proxy para descarregar
# objetos arbitrários do bucket. O manifesto só pode apontar para estes
# artefactos, dentro do prefixo do próprio post.
EXPECTED_FILES = {
    "image": "image.png",
    "caption": "caption.txt",
    "thumbnail": "thumbnail.webp",
}
MAX_VERIFIABLE_FILE_BYTES = 15 * 1024 * 1024
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


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

        expected_filename = EXPECTED_FILES.get(name)
        expected_key = (
            f"posts/{post_id}/{expected_filename}" if expected_filename else None
        )
        if expected_key is None or b2_key != expected_key:
            results.append(
                FileVerification(
                    name=str(name),
                    b2_key=str(b2_key),
                    claimed_sha256=str(claimed),
                    actual_sha256=None,
                    size_bytes=None,
                    matches=False,
                    error="O manifesto contém uma chave B2 fora do prefixo permitido.",
                )
            )
            continue
        if not isinstance(claimed, str) or not _SHA256_RE.fullmatch(claimed):
            results.append(
                FileVerification(
                    name=str(name),
                    b2_key=b2_key,
                    claimed_sha256=str(claimed),
                    actual_sha256=None,
                    size_bytes=None,
                    matches=False,
                    error="O manifesto contém um SHA-256 inválido.",
                )
            )
            continue

        try:
            backend = get_backend()
            metadata = backend.head(b2_key)
            if metadata is None:
                raise FileNotFoundError("objeto inexistente")
            remote_size = int(metadata.size)
            if remote_size > MAX_VERIFIABLE_FILE_BYTES:
                results.append(
                    FileVerification(
                        name=str(name),
                        b2_key=b2_key,
                        claimed_sha256=claimed,
                        actual_sha256=None,
                        size_bytes=remote_size,
                        matches=False,
                        error=(
                            "O ficheiro excede o limite de segurança para "
                            "verificação pública."
                        ),
                    )
                )
                continue
            data = backend.get(b2_key)
        except Exception as exc:
            results.append(
                FileVerification(
                    name=str(name), b2_key=b2_key, claimed_sha256=claimed,
                    actual_sha256=None, size_bytes=None, matches=False,
                    error=f"Não foi possível obter do B2: {exc}",
                )
            )
            continue

        actual = sha256_hex(data)
        results.append(
            FileVerification(
                name=str(name), b2_key=b2_key, claimed_sha256=claimed,
                actual_sha256=actual, size_bytes=len(data), matches=actual == claimed,
            )
        )

    return VerificationReport(
        post_id=post_id,
        verified_at=datetime.now(timezone.utc).isoformat(),
        files=results,
    )
