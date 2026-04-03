from pathlib import Path
import re

import chromadb

from app.core.exceptions import ExternalServiceError
from app.modules.rag.constants import DEFAULT_EMBEDDING_MODEL
from app.modules.rag.model_manager import ModelManager
from app.shared.settings.config import settings


class OllamaEmbeddingFunction:
    def __init__(self, manager: ModelManager, model: str) -> None:
        self._manager = manager
        self._model = model

    def __call__(self, input: list[str]) -> list[list[float]]:
        return self._manager.embed(input, model=self._model)


class ChromaGateway:
    def __init__(self) -> None:
        from app.shared.settings.runtime_settings import RuntimeSettingsService

        self.model_manager = ModelManager()
        runtime_settings = RuntimeSettingsService.get_settings()
        self.embedding_model = self.model_manager.resolve_embedding_model(
            runtime_settings.get("embedding_model", DEFAULT_EMBEDDING_MODEL)
        )
        self.chroma_client = None
        self.collection = None
        self.chroma_error: Exception | None = None
        self._init_chroma()

    @classmethod
    def _collection_name(cls, embedding_model: str) -> str:
        suffix = re.sub(r"[^a-z0-9]+", "_", embedding_model.lower()).strip("_")
        return f"andozai_docs_{suffix or 'default'}"

    def get_embedding_function(self):
        return OllamaEmbeddingFunction(self.model_manager, self.embedding_model)

    def _init_chroma(self) -> None:
        if self.collection is not None or self.chroma_error is not None:
            return
        ef = self.get_embedding_function()
        collection_name = self._collection_name(self.embedding_model)
        attempts = [
            lambda: chromadb.HttpClient(
                host=settings.CHROMA_HOST, port=settings.CHROMA_PORT
            ),
        ]
        if settings.ENVIRONMENT == "development":
            persist_dir = Path(settings.CHROMA_PERSIST_DIR)
            if not persist_dir.is_absolute():
                backend_dir = Path(__file__).resolve().parents[3]
                persist_dir = backend_dir / persist_dir
            persist_dir.mkdir(parents=True, exist_ok=True)
            attempts.append(lambda: chromadb.PersistentClient(path=str(persist_dir)))
            tmp_dir = Path("/tmp/andozai-chroma")
            tmp_dir.mkdir(parents=True, exist_ok=True)
            attempts.append(lambda: chromadb.PersistentClient(path=str(tmp_dir)))
            attempts.append(chromadb.EphemeralClient)
        last_error: Exception | None = None
        for create_client in attempts:
            try:
                client = create_client()
                collection = client.get_or_create_collection(
                    name=collection_name,
                    embedding_function=ef,
                )
                self.chroma_client = client
                self.collection = collection
                self.chroma_error = None
                return
            except Exception as exc:
                last_error = exc
        self.chroma_error = last_error or RuntimeError("Failed to initialize ChromaDB")
        self.collection = None

    def add_documents(
        self, documents: list[str], metadatas: list[dict], ids: list[str]
    ) -> None:
        self._init_chroma()
        if self.collection is None:
            raise ExternalServiceError(
                "ChromaDB is unavailable",
                service="ChromaDB",
                status_code=503,
                cause=self.chroma_error,
            )
        try:
            self.collection.add(documents=documents, metadatas=metadatas, ids=ids)
        except ExternalServiceError:
            raise
        except Exception as exc:
            raise ExternalServiceError(
                "ChromaDB request failed",
                service="ChromaDB",
                status_code=503,
                cause=exc,
            ) from exc

    def delete_documents(self, ids: list[str]) -> None:
        self._init_chroma()
        if self.collection is None:
            raise ExternalServiceError(
                "ChromaDB is unavailable",
                service="ChromaDB",
                status_code=503,
                cause=self.chroma_error,
            )
        if ids:
            try:
                self.collection.delete(ids=ids)
            except Exception as exc:
                raise ExternalServiceError(
                    "ChromaDB request failed",
                    service="ChromaDB",
                    status_code=503,
                    cause=exc,
                ) from exc

    def query_documents(
        self, query_text: str, n_results: int = 5, where: dict | None = None
    ) -> dict:
        self._init_chroma()
        if self.collection is None:
            raise ExternalServiceError(
                "ChromaDB is unavailable",
                service="ChromaDB",
                status_code=503,
                cause=self.chroma_error,
            )
        query_kwargs = {"query_texts": [query_text], "n_results": n_results}
        if where:
            query_kwargs["where"] = where
        try:
            return self.collection.query(**query_kwargs)
        except ExternalServiceError:
            raise
        except Exception as exc:
            raise ExternalServiceError(
                "ChromaDB request failed",
                service="ChromaDB",
                status_code=503,
                cause=exc,
            ) from exc
