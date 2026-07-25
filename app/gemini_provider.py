"""Gemini no Vertex AI Express, preservando o pipeline Genblaze.

O modo Express usa a combinação `vertexai=True` com uma chave API. A imagem
continua a ser gerada dentro de um Provider do Genblaze, portanto o manifesto
e a proveniência permanecem reais e auditáveis.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any

from genblaze_core._utils import local_file_url
from genblaze_core.models.asset import Asset
from genblaze_core.models.enums import Modality
from genblaze_core.models.step import Step
from genblaze_core.providers import (
    ModelRegistry,
    ModelSpec,
    ProviderCapabilities,
    RetryPolicy,
    SyncProvider,
)
from genblaze_core.runnable.config import RunnableConfig

from app.config import VERTEX_EXPRESS_API_KEY


class GeminiError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def get_vertex_client():
    if not VERTEX_EXPRESS_API_KEY:
        raise GeminiError("VERTEX_EXPRESS_API_KEY não configurada.")

    try:
        from google import genai
    except ImportError as exc:
        raise GeminiError(
            "google-genai não está instalado. Executa: pip install google-genai"
        ) from exc

    return genai.Client(vertexai=True, api_key=VERTEX_EXPRESS_API_KEY)


def generate_json(
    model: str,
    prompt: str,
    *,
    temperature: float = 0.0,
    max_output_tokens: int = 400,
    media: tuple[bytes, str] | None = None,
) -> tuple[dict, str]:
    """Gera JSON estruturado e devolve também o texto bruto do modelo."""
    try:
        from google.genai import types

        contents: Any = prompt
        if media is not None:
            data, mime_type = media
            contents = [
                prompt,
                types.Part.from_bytes(data=data, mime_type=mime_type),
            ]

        response = get_vertex_client().models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            ),
        )
        raw = (response.text or "").strip()
        if not raw:
            raise GeminiError("Gemini devolveu uma resposta vazia.")
        return json.loads(raw), raw
    except GeminiError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise GeminiError(f"Gemini não devolveu JSON válido: {exc}") from exc
    except Exception as exc:
        raise GeminiError(f"Falha no Gemini Vertex AI Express: {exc}") from exc


_FALLBACK_MODEL = ModelSpec(model_id="*", modality=Modality.IMAGE)


class VertexExpressImageProvider(SyncProvider):
    """Provider Genblaze para imagem do Gemini via Vertex AI Express."""

    name = "google-vertex-express"

    @classmethod
    def create_registry(cls) -> ModelRegistry:
        return ModelRegistry(fallback=_FALLBACK_MODEL)

    def __init__(
        self,
        api_key: str | None = None,
        *,
        output_dir: str | Path | None = None,
        models: ModelRegistry | None = None,
        retry_policy: RetryPolicy | None = None,
        probe_cache_ttl: float | None = None,
        probe_cache_max_entries: int | None = None,
    ):
        super().__init__(
            models=models,
            retry_policy=retry_policy,
            probe_cache_ttl=probe_cache_ttl,
            probe_cache_max_entries=probe_cache_max_entries,
        )
        self._api_key = api_key or VERTEX_EXPRESS_API_KEY
        self._output_dir = Path(output_dir) if output_dir else None
        self._client: Any = None

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supported_modalities=[Modality.IMAGE],
            supported_inputs=["text"],
            models=self._models.known(),
            output_formats=["image/png", "image/jpeg", "image/webp"],
        )

    def _get_client(self):
        if not self._api_key:
            raise GeminiError("VERTEX_EXPRESS_API_KEY não configurada.")
        if self._client is None:
            try:
                from google import genai
            except ImportError as exc:
                raise GeminiError("google-genai não está instalado.") from exc
            self._client = genai.Client(vertexai=True, api_key=self._api_key)
        return self._client

    def generate(self, step: Step, config: RunnableConfig | None = None) -> Step:
        try:
            from google.genai import types

            response = self._get_client().models.generate_content(
                model=step.model,
                contents=step.prompt or "",
                config=types.GenerateContentConfig(
                    response_modalities=[types.Modality.IMAGE],
                    candidate_count=1,
                ),
            )

            parts = []
            if response.candidates and response.candidates[0].content:
                parts = response.candidates[0].content.parts or []

            image_part = next(
                (part for part in parts if getattr(part, "inline_data", None)),
                None,
            )
            if image_part is None:
                raise GeminiError(
                    "Gemini não devolveu imagem; o pedido pode ter sido "
                    "bloqueado pelos filtros de segurança."
                )

            image_bytes = image_part.inline_data.data
            mime_type = image_part.inline_data.mime_type or "image/png"
            suffix = {
                "image/jpeg": ".jpg",
                "image/webp": ".webp",
            }.get(mime_type, ".png")

            if self._output_dir:
                self._output_dir.mkdir(parents=True, exist_ok=True)
                path = self._output_dir / f"{step.step_id}{suffix}"
            else:
                fd, tmp = tempfile.mkstemp(suffix=suffix)
                os.close(fd)
                path = Path(tmp)
            path.write_bytes(image_bytes)

            step.assets.append(
                Asset(
                    url=local_file_url(path.resolve()),
                    media_type=mime_type,
                    sha256=hashlib.sha256(image_bytes).hexdigest(),
                )
            )
            step.provider_payload = {
                "google_vertex_express": {
                    "model": step.model,
                    "response_modalities": ["IMAGE"],
                }
            }
            self._apply_registry_pricing(step)
            return step
        except GeminiError:
            raise
        except Exception as exc:
            raise GeminiError(
                f"Falha na geração de imagem pelo Gemini: {exc}"
            ) from exc
