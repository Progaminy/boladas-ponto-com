"""Upload para o Backblaze B2 nas chaves exatas exigidas pelo concurso
(posts/<post_id>/...), com verificação real pós-upload. Nunca marca um
ficheiro como armazenado sem confirmar via head() no bucket."""

import hashlib
from dataclasses import dataclass

from genblaze_s3 import S3StorageBackend

from app.config import B2_APP_KEY, B2_BUCKET, B2_KEY_ID, b2_configured


class StorageError(RuntimeError):
    """Levantado quando um upload não pôde ser confirmado no B2."""


@dataclass(frozen=True)
class UploadedFile:
    key: str
    content_type: str
    size: int
    sha256: str
    url: str


_backend: S3StorageBackend | None = None


def get_backend() -> S3StorageBackend:
    global _backend
    if not b2_configured():
        raise StorageError(
            "Backblaze B2 não está configurado (B2_KEY_ID/B2_APP_KEY/B2_BUCKET em falta)."
        )
    if _backend is None:
        _backend = S3StorageBackend.for_backblaze(
            B2_BUCKET, key_id=B2_KEY_ID, app_key=B2_APP_KEY
        )
    return _backend


def post_key(post_id: str, filename: str) -> str:
    return f"posts/{post_id}/{filename}"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def upload_and_verify(key: str, data: bytes, content_type: str) -> UploadedFile:
    """Envia `data` para `key` no B2 e confirma o upload com head() antes de
    devolver sucesso. Levanta StorageError se a confirmação falhar ou o
    tamanho não corresponder ao que foi enviado — nunca finge sucesso."""
    backend = get_backend()
    digest = sha256_hex(data)

    backend.put(key, data, content_type=content_type)

    meta = backend.head(key)
    if meta is None:
        raise StorageError(f"Upload não confirmado: {key} não existe no B2 após o put().")
    if meta.size != len(data):
        raise StorageError(
            f"Upload corrompido: {key} tem {meta.size} bytes no B2, "
            f"esperado {len(data)}."
        )

    return UploadedFile(
        key=key,
        content_type=content_type,
        size=len(data),
        sha256=digest,
        url=backend.get_durable_url(key),
    )
