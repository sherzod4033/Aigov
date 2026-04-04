import re
from typing import Dict, List

from app.core.exceptions import ExternalServiceError
from app.modules.rag.constants import DEFAULT_CHAT_MODEL
from app.modules.rag.model_manager import ModelManager
from app.modules.rag.text_utils import sanitize_answer_text


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
            "to be a standalone search query that contains all necessary keywords from the context.\n"
            "Rules:\n1) Keep it concise (max 10 words).\n2) Just return the refined query, no explanations.\n"
            "3) If the question is already standalone, return it as is.\n\n"
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
        assistant_name: str = "KnowledgeAI",
        answer_rules: str | None = None,
        no_data_answer: str | None = None,
    ) -> str:
        resolved_model = self.model_manager.resolve_chat_model(model)
        context_str = "\n\n".join(context)
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
            f"You are {assistant_name}. Answer the user question based on the provided context and history.\n"
            f"Rules:\n1) {answer_rules}\n2) Adaptive Style: You can adapt the explanation style if the user asks, but do not invent facts.\n"
            f'3) If the context does not contain the answer to the core question, respond exactly with: "{no_data_answer}".\n'
            "4) Maintain conversation flow using chat history.\n\n"
            f"History:\n{history_str or 'No history'}\n\nContext:\n{context_str}\n\nQuestion: {query}\nAnswer:"
        )
        try:
            draft_answer = await self.model_manager.chat(
                model=resolved_model,
                messages=[{"role": "user", "content": prompt}],
            )
        except ExternalServiceError as exc:
            if resolved_model != DEFAULT_CHAT_MODEL:
                try:
                    draft_answer = await self.model_manager.chat(
                        model=DEFAULT_CHAT_MODEL,
                        messages=[{"role": "user", "content": prompt}],
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
