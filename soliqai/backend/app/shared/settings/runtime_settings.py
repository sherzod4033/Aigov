import json
from pathlib import Path
from typing import Any

from app.core.exceptions import ExternalServiceError
from app.domain_profiles import list_domain_profiles
from app.modules.rag.model_manager import ModelManager
from app.shared.settings.config import settings


class RuntimeSettingsService:
    DEFAULTS: dict[str, Any] = {
        "chat_model": settings.OLLAMA_MODEL_CHAT,
        "embedding_model": settings.OLLAMA_MODEL_EMBEDDING,
        "top_k": 5,
        "default_domain_profile": "tax",
    }

    @classmethod
    def _settings_path(cls) -> Path:
        backend_dir = Path(__file__).resolve().parents[3]
        path = backend_dir / "data" / "runtime_settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def available_models(cls) -> list[str]:
        return cls.model_catalog()["available_models"]

    @classmethod
    def model_catalog(cls) -> dict[str, Any]:
        ollama_available = True
        ollama_error: str | None = None
        candidates: list[str] = []

        try:
            candidates.extend(ModelManager().list_ollama_models())
        except ExternalServiceError as exc:
            ollama_available = False
            ollama_error = exc.message

        available_embedding_models = cls._unique_models(candidates)
        available_chat_models = list(available_embedding_models)
        return {
            "available_models": cls._unique_models(
                [*available_chat_models, *available_embedding_models]
            ),
            "available_chat_models": available_chat_models,
            "available_embedding_models": available_embedding_models,
            "ollama_available": ollama_available,
            "ollama_error": ollama_error,
        }

    @classmethod
    def get_settings(cls) -> dict[str, Any]:
        path = cls._settings_path()
        if not path.exists():
            return dict(cls.DEFAULTS)

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return dict(cls.DEFAULTS)

        merged = dict(cls.DEFAULTS)
        merged.update(data if isinstance(data, dict) else {})
        legacy_model = str(merged.get("model") or "").strip()
        merged["chat_model"] = str(merged.get("chat_model") or legacy_model).strip()
        merged["embedding_model"] = str(merged.get("embedding_model") or "").strip()
        merged["top_k"] = cls._normalize_top_k(merged.get("top_k"))
        if not merged["chat_model"]:
            merged["chat_model"] = cls.DEFAULTS["chat_model"]
        if not merged["embedding_model"]:
            merged["embedding_model"] = cls.DEFAULTS["embedding_model"]
        merged["model"] = merged["chat_model"]
        merged["default_domain_profile"] = cls._normalize_domain_profile(
            merged.get("default_domain_profile")
        )
        return merged

    @classmethod
    def update_settings(cls, patch: dict[str, Any]) -> dict[str, Any]:
        current = cls.get_settings()

        if "chat_model" in patch or "model" in patch:
            selected_model = str(
                patch.get("chat_model") or patch.get("model") or ""
            ).strip()
            if not selected_model:
                raise ValueError("Chat model must not be empty")
            if selected_model not in cls.model_catalog()["available_chat_models"]:
                raise ValueError(f"Unsupported chat model: {selected_model}")
            current["chat_model"] = selected_model
            current["model"] = selected_model
        if "embedding_model" in patch:
            embedding_model = str(patch["embedding_model"] or "").strip()
            if not embedding_model:
                raise ValueError("Embedding model must not be empty")
            if embedding_model not in cls.model_catalog()["available_embedding_models"]:
                raise ValueError(f"Unsupported embedding model: {embedding_model}")
            current["embedding_model"] = embedding_model
        if "top_k" in patch:
            current["top_k"] = cls._normalize_top_k(patch["top_k"])
        if "default_domain_profile" in patch:
            current["default_domain_profile"] = cls._normalize_domain_profile(
                patch["default_domain_profile"]
            )

        path = cls._settings_path()
        path.write_text(
            json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return current

    @staticmethod
    def _normalize_top_k(value: Any) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return 5
        return max(1, min(number, 20))

    @staticmethod
    def _normalize_domain_profile(value: Any) -> str:
        profile = str(value or "").strip().lower()
        available = set(list_domain_profiles())
        return profile if profile in available else "tax"

    @staticmethod
    def _unique_models(candidates: list[str]) -> list[str]:
        seen: set[str] = set()
        unique_models: list[str] = []
        for model in candidates:
            normalized = str(model or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique_models.append(normalized)
        return unique_models
