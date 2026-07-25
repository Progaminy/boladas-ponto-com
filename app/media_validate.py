"""Validação real da média enviada pelo utilizador para um produto: até 4
fotos e 1 vídeo de 30 segundos. Nunca confia só na extensão do ficheiro ou no
content_type declarado pelo browser — reabre a imagem com Pillow e mede a
duração real do vídeo com ffprobe."""

import io
import json
import shutil
import subprocess
import tempfile

from PIL import Image

MAX_PHOTOS = 4
MAX_VIDEOS = 1
MAX_VIDEO_SECONDS = 30
VIDEO_DURATION_TOLERANCE_SECONDS = 1.5

MAX_PHOTO_SIZE_BYTES = 8 * 1024 * 1024
MAX_VIDEO_SIZE_BYTES = 40 * 1024 * 1024

ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/webm", "video/quicktime"}


class MediaValidationError(ValueError):
    pass


def validate_photo(data: bytes, content_type: str) -> None:
    if content_type not in ALLOWED_PHOTO_TYPES:
        raise MediaValidationError(f"Tipo de imagem não suportado: {content_type}")
    if len(data) > MAX_PHOTO_SIZE_BYTES:
        raise MediaValidationError("Foto excede o tamanho máximo de 8 MB.")
    try:
        Image.open(io.BytesIO(data)).verify()
    except Exception as exc:
        raise MediaValidationError(f"Ficheiro não é uma imagem válida: {exc}") from exc


def ffprobe_available() -> bool:
    return shutil.which("ffprobe") is not None


def get_video_duration_seconds(data: bytes) -> float:
    if not ffprobe_available():
        raise MediaValidationError(
            "Não foi possível verificar a duração do vídeo (ffprobe indisponível no servidor)."
        )
    with tempfile.NamedTemporaryFile(suffix=".mp4") as tmp:
        tmp.write(data)
        tmp.flush()
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", tmp.name],
            capture_output=True, text=True, timeout=20,
        )
    if result.returncode != 0:
        raise MediaValidationError(f"Não foi possível ler o vídeo: {result.stderr.strip()[:200]}")
    try:
        return float(json.loads(result.stdout)["format"]["duration"])
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        raise MediaValidationError("Não foi possível determinar a duração do vídeo.") from exc


def validate_video(data: bytes, content_type: str) -> float:
    if content_type not in ALLOWED_VIDEO_TYPES:
        raise MediaValidationError(f"Tipo de vídeo não suportado: {content_type}")
    if len(data) > MAX_VIDEO_SIZE_BYTES:
        raise MediaValidationError("Vídeo excede o tamanho máximo de 40 MB.")
    duration = get_video_duration_seconds(data)
    if duration > MAX_VIDEO_SECONDS + VIDEO_DURATION_TOLERANCE_SECONDS:
        raise MediaValidationError(
            f"Vídeo tem {duration:.1f}s — o máximo permitido é {MAX_VIDEO_SECONDS}s."
        )
    return duration
