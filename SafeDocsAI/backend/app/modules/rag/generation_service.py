import re
from typing import Any, Dict, List

from app.core.exceptions import ExternalServiceError
from app.modules.rag.constants import DEFAULT_CHAT_MODEL
from app.modules.rag.model_manager import ModelManager
from app.modules.rag.text_utils import sanitize_answer_text


def format_context_for_llm(
    context: List[str],
    context_metadata: List[Dict[str, Any]] | None = None,
) -> str:
    """Format context chunks separating system metadata from document text."""
    if not context:
        return ""
    parts: list[str] = []
    for i, text in enumerate(context):
        meta = (context_metadata[i] if context_metadata and i < len(context_metadata) else {}) or {}

        # Strip LLM metadata prefix: "{llm_ctx} [{doc_name | section | стр. N}] {original_text}"
        bracket_match = re.search(r'\[([^\]]+)\]\s*', text)
        if bracket_match:
            original_text = text[bracket_match.end():].strip()
        else:
            original_text = text.strip()

        doc_name = meta.get("doc_name") or ""
        chunk_xml = (
            f"<chunk>\n"
            f"<file_name>{doc_name}</file_name>\n"
            f"<original_text>\n{original_text}\n</original_text>\n"
            f"</chunk>"
        )
        parts.append(chunk_xml)
    return "\n\n".join(parts)


class GenerationService:
    def __init__(self) -> None:
        self.model_manager = ModelManager()

    @staticmethod
    def _fallback_from_context(context: List[str], no_data_answer: str) -> str:
        sentences: list[str] = []
        for chunk in context:
            for sentence in re.split(r"(?<=[.!?])\s+|\n+", chunk or ""):
                cleaned = " ".join(sentence.split()).strip()
                if cleaned:
                    sentences.append(cleaned)
            if len(sentences) >= 2:
                break
        if not sentences:
            return no_data_answer
        return " ".join(sentences[:2]).strip()

    async def condense_query(
        self,
        query: str,
        chat_history: List[Dict[str, str]],
        model: str = DEFAULT_CHAT_MODEL,
    ) -> str:
        if not chat_history:
            return query
        history_str = ""
        for msg in chat_history[-3:]:
            role = "User" if msg["role"] == "user" else "AI"
            history_str += f"{role}: {msg['content']}\n"
        prompt = (
            "Given the following conversation and a follow-up question, rephrase the follow-up question "
            "to be a standalone search query that contains all necessary context.\n\n"
            "Rules:\n"
            "1) Explicitly replace all pronouns (he, it, they, this) and list references "
            '(e.g., "the first", "the third") with the exact and full entity names from the chat history.\n'
            "2) Output the standalone query in the EXACT same language as the user's follow-up question (e.g., Russian).\n"
            "3) Just return the refined query, no explanations, no quotes.\n"
            "4) If the question is already standalone, return it as is without changes.\n\n"
            f"Chat History:\n{history_str}\nFollow-up Question: {query}\nStandalone Query:"
        )
        try:
            condensed = await self.model_manager.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )
            condensed = condensed.strip().strip('"')
            return query if not condensed or len(condensed.split()) > 20 else condensed
        except ExternalServiceError:
            return query

    async def generate_answer(
        self,
        query: str,
        context: List[str],
        chat_history: List[Dict[str, str]] | None = None,
        language: str = "ru",
        model: str = DEFAULT_CHAT_MODEL,
        assistant_name: str = "SafeDocsAI",
        answer_rules: str | None = None,
        no_data_answer: str | None = None,
        context_metadata: List[Dict[str, Any]] | None = None,
    ) -> str:
        from app.services.runtime_settings_service import RuntimeSettingsService
        runtime_settings = RuntimeSettingsService.get_settings()
        chat_num_ctx = runtime_settings.get("chat_model_num_ctx", 20000)

        resolved_model = self.model_manager.resolve_chat_model(model)
        context_str = format_context_for_llm(context, context_metadata)
        no_data_answer = no_data_answer or (
            "Маълумот дар манбаъҳои интихобшуда мавҷуд нест / Ответ не найден в выбранных источниках"
            if language == "tj"
            else "Ответ не найден в выбранных источниках / Маълумот дар манбаъҳои интихобшуда мавҷуд нест"
        )
        answer_rules = answer_rules or (
            "Use ONLY factual information from the provided context. "
            "If the context does not contain the answer to the core question, return the exact no-data message."
        )
        history_str = ""
        if chat_history:
            for msg in chat_history[-3:]:
                role = "User" if msg["role"] == "user" else "AI"
                history_str += f"{role}: {msg['content']}\n"

        prompt = (
            f"You are {assistant_name}, a document-based question answering assistant.\n"
            f"Answer the user's question using ONLY the provided context and conversation history.\n\n"
            f"Rules:\n"
            f"1) {answer_rules}\n"
            f"2) Find the answer ONLY inside the <original_text> tags. Do not use any other part of the context as a source of facts.\n"
            f"3) For every fact or figure you state, you MUST cite the source file name in parentheses. The file name is located strictly between the <file_name> and </file_name> tags. Never use any other words or phrases from the context as a citation. Example: (payom2005.txt).\n"
            f"4) Reply in the same language the user used (Russian, Tajik, or other). Do not switch languages.\n"
            f"5) You may adapt your explanation style on request, but never invent facts.\n"
            f'6) If the context does not contain the answer, reply exactly: "{no_data_answer}".\n'
            f"7) Maintain conversation flow using the history.\n"
            f"8) If you found information for only part of the question, give a partial answer — state what you found and clearly note what is missing from the context.\n\n"
            f"History:\n{history_str or 'No history'}\n\nContext:\n{context_str}\n\nQuestion: {query}\nAnswer:"
        )

        try:
            draft_answer = await self.model_manager.chat(
                model=resolved_model,
                messages=[{"role": "user", "content": prompt}],
                num_ctx=chat_num_ctx,
            )
        except ExternalServiceError as exc:
            if resolved_model != DEFAULT_CHAT_MODEL:
                try:
                    draft_answer = await self.model_manager.chat(
                        model=DEFAULT_CHAT_MODEL,
                        messages=[{"role": "user", "content": prompt}],
                        num_ctx=chat_num_ctx,
                    )
                except ExternalServiceError as fallback_exc:
                    raise ExternalServiceError(
                        "Chat provider is unavailable",
                        service=fallback_exc.service,
                        status_code=fallback_exc.status_code,
                        cause=fallback_exc,
                    ) from fallback_exc
            else:
                raise ExternalServiceError(
                    "Chat provider is unavailable",
                    service=exc.service,
                    status_code=exc.status_code,
                    cause=exc,
                ) from exc

        answer = sanitize_answer_text(draft_answer)
        if not answer:
            return self._fallback_from_context(context, no_data_answer)
        return answer
