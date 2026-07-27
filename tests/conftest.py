"""Proteções comuns da suite: testes unitários nunca gastam IA nem escrevem no B2."""

import pytest

from app.pipeline import CaptionResult, GenerationError
from app.storage import UploadedFile, sha256_hex


@pytest.fixture(autouse=True)
def no_external_generation_or_storage(monkeypatch):
    """Mantém os testes HTTP determinísticos e totalmente locais.

    O teste de integração real chama os módulos de pipeline/armazenamento
    diretamente e só corre com ``RUN_LIVE_INTEGRATION_TESTS=1``; portanto este
    isolamento das referências importadas pelo router não o interfere.
    """
    from app.routers import posts as posts_router

    def fake_caption(*args, **kwargs):
        return CaptionResult(
            caption="Legenda determinística de teste.",
            call_to_action="Contacta-nos!",
            hashtags=["boladas", "teste"],
            provider="test-local",
            model="fixture-sem-rede",
        )

    def no_image(*args, **kwargs):
        raise GenerationError("Imagem desativada na suite local.")

    def fake_upload(key, data, content_type):
        return UploadedFile(
            key=key,
            content_type=content_type,
            size=len(data),
            sha256=sha256_hex(data),
            url=f"https://fake-b2.example/{key}",
        )

    monkeypatch.setattr(posts_router, "generate_caption", fake_caption)
    monkeypatch.setattr(posts_router, "generate_image", no_image)
    monkeypatch.setattr(posts_router, "upload_and_verify", fake_upload)
