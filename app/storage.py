"""Armazenamento de ficheiros no Backblaze B2 via API S3 compatível."""

import hashlib
from dataclasses import dataclass
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import (
    B2_APP_KEY,
    B2_BUCKET,
    B2_KEY_ID,
    B2_MEDIA_PREFIX,
    B2_REGION,
    b2_configured,
)


class StorageError(RuntimeError):
    pass


@dataclass(frozen=True)
class ObjectMeta:
    size: int


@dataclass(frozen=True)
class UploadedFile:
    key: str
    content_type: str
    size: int
    sha256: str
    url: str


class B2StorageBackend:
    def __init__(self) -> None:
        endpoint = f"https://s3.{B2_REGION}.backblazeb2.com"
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name=B2_REGION,
            aws_access_key_id=B2_KEY_ID,
            aws_secret_access_key=B2_APP_KEY,
            config=Config(signature_version="s3v4"),
        )

    def put(self, key: str, data: bytes, *, content_type: str) -> None:
        self.client.put_object(
            Bucket=B2_BUCKET,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    def head(self, key: str) -> ObjectMeta | None:
        try:
            response = self.client.head_object(Bucket=B2_BUCKET, Key=key)
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise
        return ObjectMeta(size=int(response.get("ContentLength", 0)))

    def get(self, key: str) -> bytes:
        response = self.client.get_object(Bucket=B2_BUCKET, Key=key)
        return response["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=B2_BUCKET, Key=key)

    def get_durable_url(self, key: str) -> str:
        escaped = quote(key, safe="/")
        return f"https://{B2_BUCKET}.s3.{B2_REGION}.backblazeb2.com/{escaped}"


_backend: B2StorageBackend | None = None


def get_backend() -> B2StorageBackend:
    global _backend
    if not b2_configured():
        raise StorageError(
            "Backblaze B2 não está configurado (B2_KEY_ID/B2_APP_KEY/B2_BUCKET em falta)."
        )
    if _backend is None:
        _backend = B2StorageBackend()
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
    backend = get_backend()
    local_digest = sha256_hex(data)

    try:
        backend.put(key, data, content_type=content_type)
        meta = backend.head(key)
    except StorageError:
        raise
    except Exception as exc:
        raise StorageError(f"O Backblaze B2 recusou o envio de {key}: {exc}") from exc

    if meta is None:
        raise StorageError(f"Upload não confirmado: {key} não existe no B2 após o envio.")
    if meta.size != len(data):
        raise StorageError(
            f"Upload corrompido: {key} tem {meta.size} bytes no B2, esperado {len(data)}."
        )

    try:
        remote_bytes = backend.get(key)
    except Exception as exc:
        raise StorageError(f"Não foi possível confirmar {key} no B2: {exc}") from exc

    remote_digest = sha256_hex(remote_bytes)
    if remote_digest != local_digest:
        raise StorageError(
            f"Upload corrompido: SHA-256 de {key} no B2 não corresponde ao ficheiro enviado."
        )

    return UploadedFile(
        key=key,
        content_type=content_type,
        size=len(data),
        sha256=remote_digest,
        url=backend.get_durable_url(key),
    )
