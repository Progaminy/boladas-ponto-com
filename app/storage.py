"""Upload para o Backblaze B2 nas chaves exatas exigidas pelo concurso
(posts/<post_id>/...), com verificação real pós-upload. Nunca marca um
ficheiro como armazenado sem confirmar via head() no bucket."""

import hashlib
from dataclasses import dataclass

from genblaze_s3 import S3StorageBackend

from app.config import (
    B2_APP_KEY,
    B2_BUCKET,
    B2_KEY_ID,
    B2_MEDIA_PREFIX,
    b2_configured,
)


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


def user_key(user_id: str, filename: str) -> str:
    return f"{B2_MEDIA_PREFIX}users/{user_id}/{filename}"


def business_key(business_id: str, filename: str) -> str:
    return f"{B2_MEDIA_PREFIX}businesses/{business_id}/{filename}"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def upload_and_verify(key: str, data: bytes, content_type: str) -> UploadedFile:
    """Envia `data` para `key` no B2 e confirma o upload voltando a descarregar
    o objeto e recalculando o SHA-256 sobre o conteúdo realmente armazenado —
    não basta existir e ter o tamanho certo, o hash local e o hash do B2 têm
    de bater certo. Levanta StorageError em qualquer divergência: nunca finge
    uma verificação que não foi feita."""
    backend = get_backend()
    local_digest = sha256_hex(data)

    # O SDK levanta a sua própria StorageError (genblaze_core.exceptions), que
    # não é a nossa. Sem esta tradução, uma recusa do B2 — por exemplo uma
    # chave sem permissão para este prefixo — escapava a todos os `except
    # StorageError` dos chamadores e chegava ao utilizador como um 500.
    try:
        backend.put(key, data, content_type=content_type)
        meta = backend.head(key)
    except StorageError:
        raise
    except Exception as exc:
        raise StorageError(f"O Backblaze B2 recusou o envio de {key}: {exc}") from exc

    if meta is None:
        raise StorageError(f"Upload não confirmado: {key} não existe no B2 após o put().")
    if meta.size != len(data):
        raise StorageError(
            f"Upload corrompido: {key} tem {meta.size} bytes no B2, "
            f"esperado {len(data)}."
        )

    remote_bytes = backend.get(key)
    remote_digest = sha256_hex(remote_bytes)
    if remote_digest != local_digest:
        raise StorageError(
            f"Upload corrompido: SHA-256 de {key} no B2 ({remote_digest}) não "
            f"corresponde ao SHA-256 enviado ({local_digest})."
        )

    return UploadedFile(
        key=key,
        content_type=content_type,
        size=len(data),
        sha256=remote_digest,
        url=backend.get_durable_url(key),
    )
