"""Providers síncronos usados pelo pipeline Genblaze da aplicação.

O modo Express usa a combinação `vertexai=True` com uma chave API. A imagem
e a legenda continuam a ser geradas dentro de Providers do Genblaze, portanto
o manifesto e a proveniência permanecem reais e auditáveis. O SDK do
GMICloud ainda expõe chat como função, não como Provider; o adaptador de texto
abaixo coloca também essa chamada dentro do mesmo Pipeline.
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

from app.config import GEMINI_USE_VERTEX, VERTEX_EXPRESS_API_KEY


class GeminiError(RuntimeError):
    pass


# Margem mínima de tokens de saída: os tokens de raciocínio dos modelos flash
# consomem parte deste orçamento antes de o JSON sequer começar a ser escrito.
_MIN_OUTPUT_TOKENS = 2048


def _build_client(api_key: str):
    try:
        from google import genai
    except ImportError as exc:
        raise GeminiError(
            "google-genai não está instalado. Executa: pip install google-genai"
        ) from exc

    if GEMINI_USE_VERTEX:
        return genai.Client(vertexai=True, api_key=api_key)
    return genai.Client(api_key=api_key)


@lru_cache(maxsize=1)
def get_vertex_client():
    if not VERTEX_EXPRESS_API_KEY:
        raise GeminiError("VERTEX_EXPRESS_API_KEY não configurada.")
    return _build_client(VERTEX_EXPRESS_API_KEY)


def _generate_json_with_client(
    client,
    model: str,
    prompt: str,
    *,
    temperature: float = 0.0,
    max_output_tokens: int = 400,
    media: tuple[bytes, str] | None = None,
) -> tuple[dict, str]:
    """Gera JSON estruturado com um cliente Gemini já autenticado."""
    try:
        from google.genai import types

        contents: Any = prompt
        if media is not None:
            data, mime_type = media
            contents = [
                prompt,
                types.Part.from_bytes(data=data, mime_type=mime_type),
            ]

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=temperature,
                # Os modelos "flash" recentes raciocinam antes de responder e
                # esses tokens contam para o limite, pelo que um valor apertado
                # devolvia JSON truncado a meio. Damos margem para o raciocínio
                # (desativá-lo não é aceite por estes modelos).
                max_output_tokens=max(max_output_tokens, _MIN_OUTPUT_TOKENS),
            ),
        )
        raw = (response.text or "").strip()
        if not raw:
            raise GeminiError(
                "Gemini devolveu uma resposta vazia "
                f"(finish_reason={getattr(response.candidates[0], 'finish_reason', '?') if response.candidates else '?'})."
            )
        return json.loads(raw), raw
    except GeminiError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise GeminiError(f"Gemini não devolveu JSON válido: {exc}") from exc
    except Exception as exc:
        raise GeminiError(f"Falha no Gemini Vertex AI Express: {exc}") from exc


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
        return _generate_json_with_client(
            get_vertex_client(),
            model,
            prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            media=media,
        )
    except GeminiError:
        raise
    except Exception as exc:
        raise GeminiError(f"Falha no Gemini Vertex AI Express: {exc}") from exc


_IMAGE_FALLBACK_MODEL = ModelSpec(model_id="*", modality=Modality.IMAGE)
_TEXT_FALLBACK_MODEL = ModelSpec(model_id="*", modality=Modality.TEXT)


class VertexExpressImageProvider(SyncProvider):
    """Provider Genblaze para imagem do Gemini via Vertex AI Express."""

    name = "google-vertex-express"

    @classmethod
    def create_registry(cls) -> ModelRegistry:
        return ModelRegistry(fallback=_IMAGE_FALLBACK_MODEL)

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
            self._client = _build_client(self._api_key)
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


class _JsonTextProvider(SyncProvider):
    """Base para Providers que devolvem um único documento JSON em texto."""

    @classmethod
    def create_registry(cls) -> ModelRegistry:
        return ModelRegistry(fallback=_TEXT_FALLBACK_MODEL)

    def __init__(
        self,
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
        self._output_dir = Path(output_dir) if output_dir else None

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supported_modalities=[Modality.TEXT],
            supported_inputs=["text"],
            models=self._models.known(),
            output_formats=["application/json"],
        )

    def _generate_raw(self, step: Step) -> tuple[str, dict[str, Any], float | None]:
        raise NotImplementedError

    def generate(self, step: Step, config: RunnableConfig | None = None) -> Step:
        raw, provider_payload, cost_usd = self._generate_raw(step)
        raw = raw.strip()
        if not raw:
            raise RuntimeError(f"{self.name} devolveu uma resposta de texto vazia.")

        data = raw.encode("utf-8")
        if self._output_dir:
            self._output_dir.mkdir(parents=True, exist_ok=True)
            path = self._output_dir / f"{step.step_id}.json"
        else:
            fd, tmp = tempfile.mkstemp(suffix=".json")
            os.close(fd)
            path = Path(tmp)
        path.write_bytes(data)

        step.assets.append(
            Asset(
                url=local_file_url(path.resolve()),
                media_type="application/json",
                sha256=hashlib.sha256(data).hexdigest(),
                size_bytes=len(data),
            )
        )
        step.provider_payload = provider_payload
        step.cost_usd = cost_usd
        self._apply_registry_pricing(step)
        return step


class VertexExpressTextProvider(_JsonTextProvider):
    """Provider Genblaze para texto JSON do Gemini/Vertex Express."""

    name = "google-vertex-express"

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
            output_dir=output_dir,
            models=models,
            retry_policy=retry_policy,
            probe_cache_ttl=probe_cache_ttl,
            probe_cache_max_entries=probe_cache_max_entries,
        )
        self._api_key = api_key or VERTEX_EXPRESS_API_KEY
        self._client: Any = None

    def _get_client(self):
        if not self._api_key:
            raise GeminiError("VERTEX_EXPRESS_API_KEY não configurada.")
        if self._client is None:
            self._client = _build_client(self._api_key)
        return self._client

    def _generate_raw(self, step: Step) -> tuple[str, dict[str, Any], float | None]:
        _, raw = _generate_json_with_client(
            self._get_client(),
            step.model,
            step.prompt or "",
            temperature=float(step.params.get("temperature", 0.0)),
            max_output_tokens=int(step.params.get("max_output_tokens", 400)),
        )
        return (
            raw,
            {
                "google_vertex_express": {
                    "model": step.model,
                    "response_mime_type": "application/json",
                }
            },
            None,
        )


class GMICloudTextProvider(_JsonTextProvider):
    """Adapta `genblaze_gmicloud.chat()` ao contrato de Provider/Pipeline."""

    name = "gmicloud"

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
            output_dir=output_dir,
            models=models,
            retry_policy=retry_policy,
            probe_cache_ttl=probe_cache_ttl,
            probe_cache_max_entries=probe_cache_max_entries,
        )
        self._api_key = api_key

    def _generate_raw(self, step: Step) -> tuple[str, dict[str, Any], float | None]:
        # O pacote oficial ainda fornece chat como função independente. Este
        # adaptador mantém a chamada real, mas deixa execução, retries, assets e
        # manifesto sob responsabilidade do Pipeline Genblaze.
        from genblaze_gmicloud import chat

        response = chat(
            step.model,
            prompt=step.prompt or "",
            temperature=step.params.get("temperature"),
            max_tokens=step.params.get("max_tokens"),
            api_key=self._api_key,
        )
        return (
            response.text,
            {
                "gmicloud": {
                    "model": response.model,
                    "finish_reason": response.finish_reason,
                    "tokens_in": response.tokens_in,
                    "tokens_out": response.tokens_out,
                    "tokens_cached": response.tokens_cached,
                }
            },
            response.cost_usd,
        )
