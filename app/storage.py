"""Armazenamento de ficheiros no Backblaze B2 via API S3 compatível.

As operações são feitas diretamente nos objetos, sem um preflight HeadBucket.
Isso evita exigir permissões de bucket que uma Application Key restrita pode
não possuir.
"""

import hashlib
from dataclasses import dataclass
from urllib.parse import quote

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import B2_APP_KEY, B2_BUCKET, B2_KEY_ID, B2_MEDIA_PREFIX, B2_REGION, b2_configured


class StorageError(RuntimeError):
    pass


@dataclass(frozen=True)
class UploadedFile:
    key: str
    content_type: str
    size: int
    sha256: str
    url: str


@dataclass(frozen=True)
class ObjectMeta:
    size: int


class B2StorageBackend:
    def __init__(self):
        self.endpoint = f"https://s3.{B2_REGION}.backblazeb2.com"
        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=B2_KEY_ID,
            aws_secret_access_key=B2_APP_KEY,
            region_name=B2_REGION,
        )

    def put(self, key: str, data: bytes, content_type: str | None = None, **_kwargs):
        args = {"Bucket": B2_BUCKET, "Key": key, "Body": data}
        if content_type:
            args["ContentType"] = content_type
        self.client.put_object(**args)
        return key

    def head(self, key: str, **_kwargs) -> ObjectMeta | None:
        try:
            result = self.client.head_object(Bucket=B2_BUCKET, Key=key)
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if code in {"404", "NoSuchKey", "NotFound"} or status == 404:
                return None
            raise
        return ObjectMeta(size=int(result.get("ContentLength", 0)))

    def get(self, key: str, **_kwargs) -> bytes:
        result = self.client.get_object(Bucket=B2_BUCKET, Key=key)
        return result["Body"].read()

    def get_durable_url(self, key: str) -> str:
        return f"{self.endpoint}/{B2_BUCKET}/{quote(key, safe='/')}"


_backend: B2StorageBackend | None = None


def get_backend() -> B2StorageBackend:
    global _backend
    if not b2_configured():
        raise StorageError("Backblaze B2 não está configurado (B2_KEY_ID/B2_APP_KEY/B2_BUCKET/B2_REGION em falta).")
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
        if meta is None:
            raise StorageError(f"Upload não confirmado: {key} não existe no B2 após o envio.")
        if meta.size != len(data):
            raise StorageError(f"Upload incompleto: {key} tem {meta.size} bytes; esperado {len(data)}.")
        remote_bytes = backend.get(key)
    except StorageError:
        raise
    except (ClientError, BotoCoreError) as exc:
        raise StorageError(f"O Backblaze B2 recusou a operação para {key}: {exc}") from exc
    except Exception as exc:
        raise StorageError(f"Falha inesperada no armazenamento para {key}: {exc}") from exc

    remote_digest = sha256_hex(remote_bytes)
    if remote_digest != local_digest:
        raise StorageError(f"Upload corrompido: SHA-256 de {key} no B2 não corresponde ao enviado.")
    return UploadedFile(key=key, content_type=content_type, size=len(data), sha256=remote_digest, url=backend.get_durable_url(key))
