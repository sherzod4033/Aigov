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

    # check_semantic_boundary removed — replaced by deterministic HybridChunker.

    @staticmethod
    def _detect_article_reference(query: str) -> str | None:
        """
        Detects if the query is asking for a specific article or law number.
        Returns a lowercase search string for case-insensitive matching
        (e.g., "статья 80", "моддаи 2", "закон 243", "пункт 10").
        """
        q = query.lower()

        # Russian: "статья 80", "ст. 80", "80 статья", "80-ю статью", "статьей 80"
        match_ru_prefix = re.search(r"(?:стать[а-яё]*|ст\.?)\s*(\d+)", q)
        if match_ru_prefix:
            return f"статья {match_ru_prefix.group(1)}"

        match_ru_suffix = re.search(r"(\d+)\s*-?\s*(?:стать[а-яё]*|ст\.?)", q)
        if match_ru_suffix:
            return f"статья {match_ru_suffix.group(1)}"

        # Tajik: "моддаи 2", "моддаи 2.", "мод. 5", "дар моддаи 2"
        match_tj_prefix = re.search(r"(?:моддаи?|мод\.?)\s*(\d+)", q)
        if match_tj_prefix:
            return f"моддаи {match_tj_prefix.group(1)}"

        match_tj_suffix = re.search(r"(\d+)\s*(?:мақола|моддаи?)", q)
        if match_tj_suffix:
            return f"моддаи {match_tj_suffix.group(1)}"

        # Russian: "N закон", "закон N", "N-й закон", "законе N" (numbered bibliographic list item)
        match_law_suffix = re.search(r"(\d+)\s*-?(?:й|ый|ого)?\s*закон", q)
        if match_law_suffix:
            return f"закон {match_law_suffix.group(1)}"

        match_law_prefix = re.search(r"\bзакон[а-яё]*\s*(\d+)", q)
        if match_law_prefix:
            return f"закон {match_law_prefix.group(1)}"

        # Russian: "пункт N", "п. N" (numbered list item reference)
        match_punkt = re.search(r"(?:пункт[а-яё]*|п\.?)\s*(\d+)", q)
        if match_punkt:
            return f"пункт {match_punkt.group(1)}"

        match_punkt_suffix = re.search(r"(\d+)\s*-?\s*(?:пункт[а-яё]*)", q)
        if match_punkt_suffix:
            return f"пункт {match_punkt_suffix.group(1)}"

        return None

    @staticmethod
    def _boost_article_chunks(results: Dict, article_ref: str) -> Dict:
        """
        Post-retrieval re-ranking: boost chunks whose text contains the requested
        article reference (case-insensitive). Matching chunks are moved to the front
        with their original distance halved so they rank higher.
        """
        if not results.get("documents") or not results["documents"][0]:
            return results

        docs = results["documents"][0]
        ids = results["ids"][0]
        metas = results["metadatas"][0]
        dists = results["distances"][0]

        ref_lower = article_ref.lower()
        # Extract the numeric part from the reference (e.g. "243" from "закон 243")
        article_number = re.search(r"\d+", article_ref)
        number_str = article_number.group(0) if article_number else ""

        # Detect if this is a law/punkt reference (numbered list item style)
        is_list_item_ref = ref_lower.startswith(("закон ", "пункт "))

        # Match patterns: "Моддаи 2", "Статья 2", "моддаи 2", "243." (list item) etc.
        boosted = []
        normal = []

        for i, doc_text in enumerate(docs):
            text_lower = (doc_text or "").lower()
            # Check if the chunk contains the article/law reference
            contains_ref = ref_lower in text_lower
            # Also check with flexible whitespace: "моддаи  2" or "статья\n2"
            if not contains_ref and number_str:
                keyword = ref_lower.replace(number_str, "").strip()
                pattern = re.escape(keyword) + r"\s+" + re.escape(number_str) + r"\b"
                contains_ref = bool(re.search(pattern, text_lower))
            # For numbered list items ("закон N", "пункт N"), also match
            # the pattern "<number>." at the start of a line (bibliographic list format)
            if not contains_ref and is_list_item_ref and number_str:
                list_pattern = r"(?:^|\n)" + re.escape(number_str) + r"[.\s]"
                contains_ref = bool(re.search(list_pattern, text_lower))

            entry = (docs[i], ids[i], metas[i], dists[i])
            if contains_ref:
                boosted.append(entry)
            else:
                normal.append(entry)

        # Reorder: boosted first, then normal
        reordered = boosted + normal
        if not reordered:
            return results

        results["documents"] = [[e[0] for e in reordered]]
        results["ids"] = [[e[1] for e in reordered]]
        results["metadatas"] = [[e[2] for e in reordered]]
        # Halve distance for boosted chunks so they pass relevance filter more easily
        new_dists = []
        for i, entry in enumerate(reordered):
            if i < len(boosted):
                new_dists.append(entry[3] * 0.5)
            else:
                new_dists.append(entry[3])
        results["distances"] = [new_dists]

        return results

    def query_documents(self, query_text: str, n_results: int = 5) -> Dict:
        self._init_chroma()
        if self.collection is None:
            return {
                "ids": [[]],
                "documents": [[]],
                "metadatas": [[]],
                "distances": [[]],
            }

        article_ref = self._detect_article_reference(query_text)
        # When an article is referenced, fetch more chunks to increase recall,
        # then boost matching ones to the top.
        effective_n = max(n_results, 15) if article_ref else n_results

        results = self.collection.query(
            query_texts=[query_text],
            n_results=effective_n,
        )

        if article_ref:
            results = self._boost_article_chunks(results, article_ref)

        return results

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
