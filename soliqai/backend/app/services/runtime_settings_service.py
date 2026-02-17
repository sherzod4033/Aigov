import json
from pathlib import Path
from typing import Any, Dict

from app.core.config import settings


class RuntimeSettingsService:
    DEFAULTS: Dict[str, Any] = {
        "model": "gemma3n:e4b",
        "top_k": 5,
    }

    @classmethod
    def _settings_path(cls) -> Path:
        backend_dir = Path(__file__).resolve().parents[2]
        path = backend_dir / "data" / "runtime_settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def available_models(cls) -> list[str]:
        candidates = [
            "gemma3n:e4b",
            "phi3:mini",
            "gemma:2b",
            "llama3.1:8b",
        ]
        if settings.OPENAI_API_KEY and settings.OPENAI_MODEL:
            candidates.append(settings.OPENAI_MODEL)
        seen: set[str] = set()
        unique_models: list[str] = []
        for model in candidates:
            if not model or model in seen:
                continue
            seen.add(model)
            unique_models.append(model)
        return unique_models

    @classmethod
    def get_settings(cls) -> Dict[str, Any]:
        path = cls._settings_path()
        if not path.exists():
            return dict(cls.DEFAULTS)

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return dict(cls.DEFAULTS)

        merged = dict(cls.DEFAULTS)
        merged.update(data if isinstance(data, dict) else {})
        merged["top_k"] = cls._normalize_top_k(merged.get("top_k"))
        available = cls.available_models()
        if not merged.get("model") or merged["model"] not in available:
            merged["model"] = cls.DEFAULTS["model"]
        return merged

    @classmethod
    def update_settings(cls, patch: Dict[str, Any]) -> Dict[str, Any]:
        current = cls.get_settings()

        if "model" in patch and patch["model"]:
            selected_model = str(patch["model"]).strip()
            available_models = cls.available_models()
            if selected_model not in available_models:
                raise ValueError(f"Unsupported model: {selected_model}")
            current["model"] = selected_model
        if "top_k" in patch:
            current["top_k"] = cls._normalize_top_k(patch["top_k"])

        path = cls._settings_path()
        path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
        return current

    @staticmethod
    def _normalize_top_k(value: Any) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return 5
        return max(1, min(number, 20))
