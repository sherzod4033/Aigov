import chromadb
from chromadb.utils import embedding_functions
from app.core.config import settings
import ollama
from openai import AsyncOpenAI
from pathlib import Path
from typing import List, Dict
import re


# Multilingual embedding model — supports 50+ languages including Russian and Tajik.
MULTILINGUAL_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# Maximum cosine distance for a chunk to be considered relevant.
# Calibrated for the multilingual model (lower = stricter).
RELEVANCE_DISTANCE_THRESHOLD = 1.2


RU_TJ_STOPWORDS = {
    "и", "или", "а", "но", "что", "это", "этот", "эта", "эти", "такой", "такая",
    "какой", "какая", "какие", "каково", "как", "где", "когда", "почему", "зачем",
    "сколько", "ли", "же", "бы", "на", "в", "во", "к", "ко", "по", "о", "об", "от",
    "до", "для", "при", "за", "из", "у", "над", "под", "без", "с", "со", "про",
    "именно", "пожалуйста", "андоза", "чанд", "чӣ", "ин", "барои", "бо", "аз",
    "какова", "каков", "какие", "какой", "какую", "салом", "привет", "здравствуйте",
}


REASONING_MARKERS = (
    "потому", "поскольку", "так как", "согласно", "на основании", "в соответствии",
    "статья", "зеро", "чунки", "тибқи", "мувофиқи", "бар асоси",
)


TAJIK_TO_RU_HINTS = (
    (r"\bчӣ\s*тавр\b", "как"),
    (r"\bч[иӣ]\b", "как"),
    (r"\bандоз(ро|и)?\b", "налог"),
    (r"\bсупор(?:ам|ем|ад|анд|ӣ|ид|идан)\b", "уплатить"),
    (r"\bпардохт\b", "уплата"),
    (r"\bмеъёр\b", "ставка"),
    (r"\bфоиз\b", "процент"),
    (r"\bҷарима\b", "штраф"),
)


class RAGService:
    def __init__(self):
        self.chroma_client = None
        self.collection = None
        self.chroma_error: Exception | None = None

        self._init_chroma()

        self.openai_client = (
            AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            if settings.OPENAI_API_KEY
            else None
        )

    @staticmethod
    def _get_embedding_function():
        """Return a multilingual sentence-transformer embedding function for ChromaDB."""
        return embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=MULTILINGUAL_EMBEDDING_MODEL,
        )

    def _init_chroma(self) -> None:
        if self.collection is not None or self.chroma_error is not None:
            return

        ef = self._get_embedding_function()

        attempts = []
        attempts.append(
            lambda: chromadb.HttpClient(
                host=settings.CHROMA_HOST,
                port=settings.CHROMA_PORT,
            )
        )

        persist_dir = Path(settings.CHROMA_PERSIST_DIR)
        if not persist_dir.is_absolute():
            backend_dir = Path(__file__).resolve().parents[2]
            persist_dir = backend_dir / persist_dir
        persist_dir.mkdir(parents=True, exist_ok=True)
        attempts.append(lambda: chromadb.PersistentClient(path=str(persist_dir)))

        tmp_dir = Path("/tmp/soliqai-chroma")
        tmp_dir.mkdir(parents=True, exist_ok=True)
        attempts.append(lambda: chromadb.PersistentClient(path=str(tmp_dir)))

        # Last-resort fallback. Data lives in memory (lost on process restart),
        # but keeps semantic search functional when persistent storage is unavailable.
        attempts.append(chromadb.EphemeralClient)

        last_error: Exception | None = None
        for create_client in attempts:
            try:
                client = create_client()
                collection = client.get_or_create_collection(
                    name="soliqai_docs_multilingual",
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

    def add_documents(self, documents: List[str], metadatas: List[dict], ids: List[str]):
        """
        Adds documents to ChromaDB.
        """
        self._init_chroma()
        if self.collection is None:
            raise RuntimeError(f"ChromaDB unavailable: {self.chroma_error}")

        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

    def delete_documents(self, ids: List[str]) -> None:
        self._init_chroma()
        if self.collection is None:
            raise RuntimeError(f"ChromaDB unavailable: {self.chroma_error}")
        if not ids:
            return
        self.collection.delete(ids=ids)

    @staticmethod
    def normalize_query(query_text: str) -> str:
        normalized = (query_text or "").strip().lower()
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized

    @staticmethod
    def detect_language(query_text: str) -> str:
        sample = (query_text or "").lower()
        tajik_chars = ("ӯ", "қ", "ҳ", "ҷ", "ғ", "ӣ")
        if any(char in sample for char in tajik_chars):
            return "tj"
        return "ru"

    @staticmethod
    def is_prompt_injection_attempt(query_text: str) -> bool:
        lowered = (query_text or "").lower()
        patterns = (
            "ignore previous instructions",
            "forget all instructions",
            "system prompt",
            "developer message",
            "reveal prompt",
            "bypass",
            "jailbreak",
            "act as",
            "disregard above",
            "игнорируй предыдущие",
            "раскрой системный",
            "обойди ограничения",
            "фаромӯш кун дастур",
            "дастурҳоро нодида гир",
        )
        return any(pattern in lowered for pattern in patterns)

    @staticmethod
    def _looks_like_no_data(answer_text: str) -> bool:
        normalized = " ".join((answer_text or "").lower().split())
        return (
            "ответ не найден в базе" in normalized
            or "маълумот дар база мавҷуд нест" in normalized
        )

    @staticmethod
    def stem_simple(word: str) -> str:
        """Very simple suffix stripping for RU/TJ tax terms."""
        if len(word) <= 3:
            return word
        # Russian noun/adj endings
        word = re.sub(r"(ого|его|ому|ему|ыми|ими|ых|их|ая|яя|ое|ее|ый|ий|ой|а|я|о|е|ы|и|у|ю|ом|ем|ам|ям|ах|ях)$", "", word)
        # Tajik endings
        word = re.sub(r"(ро|и|ҳо|он|онӣ)$", "", word)
        return word

    @classmethod
    def tokenize(cls, text: str) -> set[str]:
        raw_tokens = re.findall(r"[\w\-]+", (text or "").lower())
        normalized: set[str] = set()
        for token in raw_tokens:
            if token not in RU_TJ_STOPWORDS:
                stemmed = cls.stem_simple(token)
                if len(stemmed) >= 2 or stemmed.isdigit():
                    normalized.add(stemmed)
            if "-" in token:
                for piece in token.split("-"):
                    if piece not in RU_TJ_STOPWORDS:
                        stemmed_piece = cls.stem_simple(piece)
                        if len(stemmed_piece) >= 2 or stemmed_piece.isdigit():
                            normalized.add(stemmed_piece)
        return normalized

    @classmethod
    def _query_tokens(cls, text: str) -> set[str]:
        return cls.tokenize(text)

    @staticmethod
    def _is_reasoning_question(query: str) -> bool:
        query_norm = (query or "").lower()
        return bool(
            re.search(
                r"\b(почему|зачем|на каком основании|чаро|барои чӣ|бо кадом асос)\b",
                query_norm,
            )
        )

    @staticmethod
    def _has_reasoning_markers(text: str) -> bool:
        lowered = (text or "").lower()
        return any(marker in lowered for marker in REASONING_MARKERS)

    @staticmethod
    def tajik_query_to_russian_hint(query_text: str) -> str:
        hinted = RAGService.normalize_query(query_text)
        for pattern, replacement in TAJIK_TO_RU_HINTS:
            hinted = re.sub(pattern, replacement, hinted, flags=re.IGNORECASE)
        hinted = re.sub(r"\s+", " ", hinted).strip()
        return hinted

    @classmethod
    def _sanitize_answer_text(cls, answer_text: str) -> str:
        text = (answer_text or "").strip()
        if not text:
            return text
        if cls._looks_like_no_data(text):
            return text

        # Remove model-generated citation blocks; sources are rendered by frontend.
        heading = re.search(
            r"(?im)^\s*(legal\s+sources(?:\s*&\s*references)?|references)\s*:?\s*$",
            text,
        )
        if heading:
            text = text[: heading.start()].strip()

        # Normalize leading answer labels.
        text = re.sub(r"(?i)^\s*(answer|ответ|ҷавоб)\s*:\s*", "", text).strip()
        return text

    @staticmethod
    def _is_numeric_question(query: str) -> bool:
        query_norm = (query or "").lower()
        return bool(
            re.search(
                r"\b(сколько|каков|какая|какой|размер|ставк|процент|фоиз|чанд|андоза|қадар)\b",
                query_norm,
            )
        )

    # Removed _extractive_fallback_answer as requested for pure semantic RAG.

    async def condense_query(self, query: str, chat_history: List[Dict[str, str]], model: str = "gemma3n:e4b") -> str:
        """
        Condenses a follow-up question into a standalone searchable query using chat history.
        """
        if not chat_history:
            return query

        history_str = ""
        for msg in chat_history[-3:]:  # Use last 3 messages for context
            role = "User" if msg["role"] == "user" else "AI"
            history_str += f"{role}: {msg['content']}\n"

        prompt = (
            "Given the following conversation and a follow-up question, rephrase the follow-up question "
            "to be a standalone search query that contains all necessary keywords from the context.\n"
            "Rules:\n"
            "1) Keep it concise (max 10 words).\n"
            "2) Just return the refined query, no explanations.\n"
            "3) If the question is already standalone, return it as is.\n\n"
            f"Chat History:\n{history_str}\n"
            f"Follow-up Question: {query}\n"
            "Standalone Query:"
        )

        try:
            # Always use local model for condensation to save OpenAI tokens and ensure privacy
            response = ollama.chat(model=model, messages=[
                {'role': 'user', 'content': prompt},
            ])
            condensed = response['message']['content'].strip().strip('"')
            # Fallback to original if condensation is empty or too long
            if not condensed or len(condensed.split()) > 20:
                return query
            return condensed
        except Exception as e:
            print(f"Query Condensation Error: {e}")
            return query

    def check_semantic_boundary(self, current_chunk: str, next_proposition: str, model: str = "gemma3n:e4b") -> bool:
        """
        Agentic decision: Should we split here?
        Returns True if a split is recommended (new topic), False if they should be merged.
        """
        # Heuristic: If implicit split by size is acceptable, we can skip LLM for very short props, 
        # but for accuracy we'll ask.
        # To save time, if current chunk is very small (<500 chars), just merge.
        if len(current_chunk) < 500:
            return False

        prompt = (
            "Analyze the semantic relationship between the Context and the Next Sentence.\n"
            "Context: \"...{context_snippet}\"\n"
            "Next Sentence: \"{next_proposition}\"\n\n"
            "Question: Does the Next Sentence start a completely new, unrelated topic compared to the Context? "
            "Answer ONLY with 'YES' (split) or 'NO' (merge)."
        )

        try:
            # Use a fast local model with low temperature
            response = ollama.chat(model=model, messages=[
                {'role': 'user', 'content': prompt.format(
                    context_snippet=current_chunk[-300:], 
                    next_proposition=next_proposition
                )},
            ], options={'temperature': 0})
            
            answer = response['message']['content'].strip().upper()
            return "YES" in answer
        except Exception as e:
            print(f"Agentic Boundary Check Error: {e}")
            return False # Fallback: merge by default if error

    @staticmethod
    def _detect_article_reference(query: str) -> str | None:
        """
        Detects if the query is asking for a specific article number.
        Returns the likely string format in the document (e.g., "СТАТЬЯ 80").
        """
        q = query.lower()
        
        # Russian: "статья 80", "ст. 80", "80 статья", "80 статье", "статью 80", "статьей 80"
        # Match "word number"
        # [яеийю] covers статья, статье, статьи, статью. 
        # For 'статьей' we can use 'стать(?:ей|[яеийю])' or simply `стать[а-я]+` but let's be specific.
        # Let's use `стать[яеийю]+` to catch endings.
        match_ru_prefix = re.search(r"\b(?:стать[яеийю]+|ст\.?)\s*(\d+)", q)
        if match_ru_prefix:
            return f"СТАТЬЯ {match_ru_prefix.group(1)}"
            
        # Match "number word"
        match_ru_suffix = re.search(r"\b(\d+)\s*(?:стать[яеийю]+|ст\.?)", q)
        if match_ru_suffix:
            return f"СТАТЬЯ {match_ru_suffix.group(1)}"
            
        # Tajik: "моддаи 80", "80 мақола"
        match_tj_prefix = re.search(r"\b(?:моддаи?|мод\.?)\s*(\d+)", q)
        if match_tj_prefix:
            return f"МОДДАИ {match_tj_prefix.group(1)}"
            
        match_tj_suffix = re.search(r"\b(\d+)\s*(?:мақола|моддаи?)", q)
        if match_tj_suffix:
            return f"МОДДАИ {match_tj_suffix.group(1)}"
            
        return None

    def query_documents(self, query_text: str, n_results: int = 5) -> Dict:
        self._init_chroma()
        if self.collection is None:
            return {
                "ids": [[]],
                "documents": [[]],
                "metadatas": [[]],
                "distances": [[]],
            }
        
        where_doc = None
        article_ref = self._detect_article_reference(query_text)
        if article_ref:
            # If specific article is requested, filter chunks to contain that string.
            # This is a heuristic to fix embedding retrieval issues for specific short articles.
            where_doc = {"$contains": article_ref}

        return self.collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where_document=where_doc
        )

    async def generate_answer(
        self, 
        query: str, 
        context: List[str], 
        chat_history: List[Dict[str, str]] = None,
        language: str = "ru", 
        model: str = "gemma3n:e4b"
    ) -> str:
        """
        Stage 1: Generate draft with local Gemma
        Stage 2: Refine with OpenAI
        """
        context_str = "\n\n".join(context)
        no_data_answer = (
            "Маълумот дар база мавҷуд нест / Ответ не найден в базе"
            if language == "tj"
            else "Ответ не найден в базе / Маълумот дар база мавҷуд нест"
        )
        
        history_str = ""
        if chat_history:
            for msg in chat_history[-3:]:
                role = "User" if msg["role"] == "user" else "AI"
                history_str += f"{role}: {msg['content']}\n"

        prompt = (
            "You are SoliqAI, a tax assistant. Answer the user question based on the provided context and history.\n"
            "Rules:\n"
            "1) Use ONLY factual information from the provided context.\n"
            "2) Adaptive Style: You can adapt the explanation style (e.g., simpler language, child-friendly) if the user asks, but do not invent new tax rules.\n"
            "3) If the context does not contain the answer to the core question, respond exactly with: "
            f"\"{no_data_answer}\".\n"
            "4) Maintain conversation flow using chat history.\n\n"
            f"History:\n{history_str or 'No history'}\n\n"
            f"Context:\n{context_str}\n\n"
            f"Question: {query}\n"
            "Answer:"
        )

        use_openai_direct = bool(self.openai_client and model == settings.OPENAI_MODEL)
        if use_openai_direct:
            try:
                openai_response = await self.openai_client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                )
                return self._sanitize_answer_text(openai_response.choices[0].message.content)
            except Exception as exc:
                print(f"OpenAI Direct Error: {exc}")
                return no_data_answer

        # Stage 1: local model (Ollama)
        draft_answer = no_data_answer
        try:
            response = ollama.chat(model=model, messages=[
                {'role': 'user', 'content': prompt},
            ])
            draft_answer = response['message']['content']
        except Exception as e:
            print(f"Ollama Error: {e}")
            # Fallback to default local model if custom model is unavailable.
            if model != "gemma3n:e4b":
                try:
                    fallback_response = ollama.chat(model="gemma3n:e4b", messages=[
                        {'role': 'user', 'content': prompt},
                    ])
                    draft_answer = fallback_response['message']['content']
                except Exception as fallback_exc:
                    print(f"Ollama Fallback Error: {fallback_exc}")
                    return no_data_answer
            else:
                return no_data_answer

        refinement_prompt = (
            "Refine the draft answer to be accurate tax advice while following the requested style.\n"
            "Rules:\n"
            "1) Keep the same language as the question (Russian or Tajik).\n"
            "2) Ensure all facts come from the provided context.\n"
            "3) If the context is missing key facts needed for the answer, return: "
            f"\"{no_data_answer}\".\n"
            "4) Preserve the tone requested by the user (e.g., if they asked for a simple explanation).\n\n"
            f"History:\n{history_str or 'No history'}\n"
            f"Question: {query}\n"
            f"Context:\n{context_str}\n"
            f"Draft answer:\n{draft_answer}\n"
        )
        
        try:
            if not self.openai_client:
                return self._sanitize_answer_text(draft_answer)

            openai_response = await self.openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": refinement_prompt}]
            )
            final_answer = openai_response.choices[0].message.content
            return self._sanitize_answer_text(final_answer)
        except Exception as e:
            print(f"OpenAI Error: {e}")
            return self._sanitize_answer_text(draft_answer)  # Fallback to Gemma result
