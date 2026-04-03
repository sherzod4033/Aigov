from typing import Any, Sequence

import ollama

from app.core.exceptions import ExternalServiceError
from app.modules.rag.constants import DEFAULT_CHAT_MODEL, DEFAULT_EMBEDDING_MODEL
from app.shared.settings.config import settings


def _is_service_unavailable(exc: Exception) -> bool:
    names = {exc.__class__.__name__}
    for attr in ("__cause__", "__context__"):
        nested = getattr(exc, attr, None)
        if nested is not None:
            names.add(nested.__class__.__name__)
    unavailable = {
        "ConnectError",
        "ConnectTimeout",
        "ConnectionError",
        "ReadTimeout",
        "RemoteProtocolError",
        "TimeoutError",
        "TimeoutException",
    }
    return any(name in unavailable for name in names)


class ModelManager:
    def __init__(self) -> None:
        self._timeout = settings.OLLAMA_TIMEOUT_SECONDS
        self._ollama_client = ollama.Client(
            host=settings.OLLAMA_API_BASE,
            timeout=self._timeout,
        )
        self._ollama_async_client = ollama.AsyncClient(
            host=settings.OLLAMA_API_BASE,
            timeout=self._timeout,
        )

    @staticmethod
    def resolve_chat_model(model: str | None = None) -> str:
        selected = (model or "").strip()
        return selected or DEFAULT_CHAT_MODEL

    @staticmethod
    def resolve_embedding_model(model: str | None = None) -> str:
        selected = (model or "").strip()
        return selected or DEFAULT_EMBEDDING_MODEL

    @staticmethod
    def _wrap_provider_error(service: str, exc: Exception) -> ExternalServiceError:
        status_code = 503 if _is_service_unavailable(exc) else 502
        message = (
            f"{service} is unavailable"
            if status_code == 503
            else f"{service} request failed"
        )
        return ExternalServiceError(
            message,
            service=service,
            status_code=status_code,
            cause=exc,
        )

    @staticmethod
    def _extract_embeddings(response: Any) -> list[list[float]]:
        embeddings = getattr(response, "embeddings", None)
        if embeddings is None and isinstance(response, dict):
            embeddings = response.get("embeddings")
        if embeddings is None:
            try:
                embeddings = response["embeddings"]
            except Exception:
                embeddings = None
        if not embeddings:
            raise ExternalServiceError(
                "Ollama returned empty embeddings",
                service="Ollama",
                status_code=502,
            )
        return [list(item) for item in embeddings]

    @staticmethod
    def _extract_model_names(response: Any) -> list[str]:
        models = getattr(response, "models", None)
        if models is None and isinstance(response, dict):
            models = response.get("models")
        if models is None:
            try:
                models = response["models"]
            except Exception:
                models = []

        names: list[str] = []
        for item in models or []:
            model_name = getattr(item, "model", None)
            if model_name is None and isinstance(item, dict):
                model_name = item.get("model")
            if isinstance(model_name, str) and model_name.strip():
                names.append(model_name.strip())
        return names

    async def chat(
        self, messages: list[dict[str, str]], model: str | None = None
    ) -> str:
        resolved_model = self.resolve_chat_model(model)

        try:
            response = await self._ollama_async_client.chat(
                model=resolved_model,
                messages=messages,
            )
        except Exception as exc:
            raise self._wrap_provider_error("Ollama", exc) from exc

        return response["message"]["content"].strip()

    def embed(
        self, texts: Sequence[str], model: str | None = None
    ) -> list[list[float]]:
        resolved_model = self.resolve_embedding_model(model)
        try:
            response = self._ollama_client.embed(
                model=resolved_model,
                input=list(texts),
            )
        except Exception as exc:
            raise self._wrap_provider_error("Ollama", exc) from exc
        return self._extract_embeddings(response)

    def list_ollama_models(self) -> list[str]:
        discovery_client = ollama.Client(
            host=settings.OLLAMA_API_BASE,
            timeout=min(self._timeout, 5.0),
        )
        try:
            response = discovery_client.list()
        except Exception as exc:
            raise self._wrap_provider_error("Ollama", exc) from exc
        return self._extract_model_names(response)
