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
    """Format context chunks with source metadata for the LLM prompt."""
    if not context:
        return ""
    if not context_metadata or len(context_metadata) != len(context):
        return "\n\n---\n\n".join(context)
    parts: list[str] = []
    for text, meta in zip(context, context_metadata):
        doc_name = meta.get("doc_name") or ""
        page = meta.get("page")
        header_parts = []
        if doc_name:
            header_parts.append(doc_name)
        if page is not None:
            header_parts.append(f"стр. {page}")
        header = f"[Источник: {', '.join(header_parts)}]" if header_parts else ""
        parts.append(f"{header}\n{text}" if header else text)
    return "\n\n---\n\n".join(parts)


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
        assistant_name: str = "KnowledgeAI",
        answer_rules: str | None = None,
        no_data_answer: str | None = None,
        context_metadata: List[Dict[str, Any]] | None = None,
    ) -> str:
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

        if language == "tj":
            prompt = (
                f"Шумо {assistant_name} ҳастед. Ба савол дар асоси контекст ва таърих ҷавоб диҳед.\n"
                f"Қоидаҳо:\n1) {answer_rules}\n"
                f"2) Шумо метавонед услуби шарҳро мутобиқ созед, аммо далелҳо наофаред.\n"
                f'3) Агар контекст ҷавоб надошта бошад, айнан бинависед: "{no_data_answer}".\n'
                f"4) Таърихи суҳбатро риоя кунед.\n"
                f"5) Агар шумо маълумотро танҳо барои як қисми савол ёфтед, ҷавоби қисмӣ диҳед: он чиро ёфтед нависед ва мушаххас қайд кунед, ки кадом маълумот дар контекст мавҷуд нест.\n\n"
                f"Таърих:\n{history_str or 'Таърих нест'}\n\nКонтекст:\n{context_str}\n\nСавол: {query}\nҶавоб:"
            )
        else:
            prompt = (
                f"Вы — {assistant_name}. Отвечайте на вопрос пользователя на основе предоставленного контекста и истории.\n"
                f"Правила:\n1) {answer_rules}\n"
                f"2) Адаптивный стиль: вы можете менять стиль объяснения по просьбе, но не выдумывайте факты.\n"
                f'3) Если контекст не содержит ответа на вопрос, ответьте точно: "{no_data_answer}".\n'
                f"4) Поддерживайте поток беседы, используя историю.\n"
                f"5) Если вы нашли информацию только для одной части вопроса пользователя, а для другой части информации в тексте нет, дайте частичный ответ. Напишите то, что нашли, и прямо укажите, какой информации не хватает в предоставленном контексте.\n\n"
                f"История:\n{history_str or 'Нет истории'}\n\nКонтекст:\n{context_str}\n\nВопрос: {query}\nОтвет:"
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
