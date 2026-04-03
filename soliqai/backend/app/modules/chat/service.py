import json
import logging
import math
import re
from time import perf_counter
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.models import Chunk, Document, Log, Notebook, User
from app.modules.chat.schemas import ChatRequest, ChatResponse, SourceItem
from app.modules.rag.constants import DEFAULT_CHAT_MODEL
from app.services.profile_resolver import resolve_profile
from app.services.rag_service import RAGService, RELEVANCE_DISTANCE_THRESHOLD
from app.services.runtime_settings_service import RuntimeSettingsService

logger = logging.getLogger(__name__)


def safe_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def is_no_data_answer(answer: str) -> bool:
    normalized = " ".join((answer or "").lower().split())
    return (
        "ответ не найден в базе" in normalized
        or "маълумот дар база мавҷуд нест" in normalized
        or "ответ не найден в выбранных источниках" in normalized
        or "маълумот дар манбаъҳои интихобшуда мавҷуд нест" in normalized
    )


async def expand_with_neighbors(
    selected_chunks: list[dict[str, Any]], session: AsyncSession
) -> list[str]:
    if not selected_chunks:
        return []
    seen_ids = {item["chunk_id"] for item in selected_chunks}
    neighbor_queries: list[tuple[int, int]] = []
    for item in selected_chunks:
        meta = item.get("metadata", {})
        doc_id = meta.get("doc_id")
        chunk_idx = meta.get("chunk_index")
        if doc_id is None or chunk_idx is None:
            continue
        for offset in (-1, 1):
            neighbor_queries.append((doc_id, chunk_idx + offset))
    neighbor_texts: dict[str, str] = {}
    if neighbor_queries:
        from sqlalchemy import and_, or_

        conditions = [
            and_(Chunk.doc_id == did, Chunk.chunk_index == cidx)
            for did, cidx in neighbor_queries
        ]
        result = await session.exec(select(Chunk).where(or_(*conditions)))
        for chunk in result.all():
            cid = str(chunk.id)
            if cid not in seen_ids:
                neighbor_texts[cid] = chunk.text
    expanded = [item["text"] for item in selected_chunks]
    expanded.extend(neighbor_texts.values())
    return expanded


def is_greeting(text: str) -> bool:
    lowered = text.lower()
    patterns = [r"\b(салом|привет|здравствуйте|добрый\s+(день|вечер|утро))\b"]
    for pattern in patterns:
        if re.search(pattern, lowered) and len(lowered.split()) <= 3:
            return True
    return False


def select_relevant_chunks(
    context: list[str],
    context_chunk_ids: list[str],
    context_metadatas: list[dict],
    context_distances: list[Any],
    allowed_doc_ids: set[int] | None = None,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for idx, chunk_text in enumerate(context):
        if not chunk_text:
            continue
        metadata = (
            context_metadatas[idx]
            if idx < len(context_metadatas) and isinstance(context_metadatas[idx], dict)
            else {}
        )
        doc_id = metadata.get("doc_id")
        if allowed_doc_ids is not None and doc_id not in allowed_doc_ids:
            continue
        distance = safe_float(
            context_distances[idx] if idx < len(context_distances) else None
        )
        candidates.append(
            {
                "idx": idx,
                "text": chunk_text,
                "metadata": metadata,
                "chunk_id": context_chunk_ids[idx]
                if idx < len(context_chunk_ids)
                else None,
                "distance": distance,
            }
        )
    if not candidates:
        return []
    relevant = [
        item
        for item in candidates
        if item["distance"] is not None
        and item["distance"] <= RELEVANCE_DISTANCE_THRESHOLD
    ]
    relevant.sort(key=lambda x: x["distance"])
    return relevant[:5]


async def chat_request(
    chat_request: ChatRequest,
    current_user: User,
    session: AsyncSession,
) -> ChatResponse:
    started = perf_counter()
    rag_service = RAGService()
    normalized_question = rag_service.normalize_query(chat_request.question)
    language = rag_service.detect_language(normalized_question)
    runtime_settings = RuntimeSettingsService.get_settings()
    top_k = runtime_settings.get("top_k", 5)
    model = runtime_settings.get("chat_model") or runtime_settings.get(
        "model", DEFAULT_CHAT_MODEL
    )

    notebook: Notebook | None = None
    if chat_request.notebook_id is not None:
        notebook = await session.get(Notebook, chat_request.notebook_id)
    if notebook is None:
        notebook_result = await session.exec(
            select(Notebook).order_by(Notebook.created_at.asc()).limit(1)
        )
        notebook = notebook_result.first()

    profile = resolve_profile(notebook=notebook, requested=chat_request.domain_profile)
    no_data_answer = profile.no_data_answer(language)

    if is_greeting(chat_request.question):
        greeting_answer = profile.greeting(language)
        empty_sources: list[SourceItem] = []
        log_entry = Log(
            question=chat_request.question,
            answer=greeting_answer,
            sources=json.dumps(
                [item.model_dump() for item in empty_sources], ensure_ascii=False
            ),
            time_ms=int((perf_counter() - started) * 1000),
            user_id=current_user.id,
            notebook_id=notebook.id if notebook else None,
            domain_profile=profile.name,
        )
        session.add(log_entry)
        await session.commit()
        await session.refresh(log_entry)
        return ChatResponse(
            answer=greeting_answer, sources=empty_sources, log_id=log_entry.id
        )

    if rag_service.is_prompt_injection_attempt(normalized_question):
        safe_answer = profile.prompt_injection_message(language)
        empty_sources: list[SourceItem] = []
        log_entry = Log(
            question=chat_request.question,
            answer=safe_answer,
            sources=json.dumps(
                [item.model_dump() for item in empty_sources], ensure_ascii=False
            ),
            time_ms=int((perf_counter() - started) * 1000),
            user_id=current_user.id,
            notebook_id=notebook.id if notebook else None,
            domain_profile=profile.name,
        )
        session.add(log_entry)
        await session.commit()
        await session.refresh(log_entry)
        return ChatResponse(
            answer=safe_answer, sources=empty_sources, log_id=log_entry.id
        )

    history_result = await session.exec(
        select(Log)
        .where(Log.user_id == current_user.id)
        .where(Log.notebook_id == (notebook.id if notebook else None))
        .order_by(Log.created_at.desc())
        .limit(5)
    )
    history_logs = sorted(history_result.all(), key=lambda x: x.created_at)
    chat_history = []
    for log in history_logs:
        chat_history.append({"role": "user", "content": log.question})
        chat_history.append({"role": "assistant", "content": log.answer})

    article_ref = rag_service._detect_article_reference(normalized_question)
    if article_ref:
        search_query = normalized_question
        logger.debug(
            f"Article reference detected ({article_ref}), skipping condensation"
        )
    else:
        search_query = await rag_service.condense_query(
            normalized_question, chat_history, model=model
        )
        logger.debug(f"Condensed Search Query: {search_query}")

    allowed_doc_ids: set[int] | None = None
    if notebook and notebook.id is not None:
        notebook_docs_result = await session.exec(
            select(Document.id).where(Document.notebook_id == notebook.id)
        )
        allowed_doc_ids = {
            doc_id for doc_id in notebook_docs_result.all() if doc_id is not None
        }

    selected_chunks: list[dict[str, Any]] = []
    search_queries = profile.search_queries(search_query, language)
    search_limit = max(top_k * 5, 20) if allowed_doc_ids else top_k
    for candidate_query in search_queries:
        logger.debug(f"Querying ChromaDB with: {candidate_query}, top_k={search_limit}")
        results = rag_service.query_documents(candidate_query, n_results=search_limit)
        results = profile.rerank_results(candidate_query, results)
        documents = results.get("documents", [])
        chunk_ids = results.get("ids", [])
        metadatas = results.get("metadatas", [])
        distances = results.get("distances", [])
        context = documents[0] if documents else []
        context_chunk_ids = chunk_ids[0] if chunk_ids else []
        context_metadatas = metadatas[0] if metadatas else []
        context_distances = distances[0] if distances else []
        selected_chunks = select_relevant_chunks(
            context=context,
            context_chunk_ids=context_chunk_ids,
            context_metadatas=context_metadatas,
            context_distances=context_distances,
            allowed_doc_ids=allowed_doc_ids,
        )
        if selected_chunks:
            break

    if not selected_chunks:
        answer_text = no_data_answer
        empty_sources: list[SourceItem] = []
        log_entry = Log(
            question=chat_request.question,
            answer=answer_text,
            sources=json.dumps(
                [item.model_dump() for item in empty_sources], ensure_ascii=False
            ),
            time_ms=int((perf_counter() - started) * 1000),
            user_id=current_user.id,
            notebook_id=notebook.id if notebook else None,
            domain_profile=profile.name,
        )
        session.add(log_entry)
        await session.commit()
        await session.refresh(log_entry)
        return ChatResponse(
            answer=answer_text, sources=empty_sources, log_id=log_entry.id
        )

    doc_id_set = {
        item["metadata"].get("doc_id")
        for item in selected_chunks
        if item["metadata"].get("doc_id") is not None
    }
    doc_name_map: dict[int, str] = {}
    if doc_id_set:
        docs_result = await session.exec(
            select(Document).where(Document.id.in_(doc_id_set))
        )
        for doc in docs_result.all():
            doc_name_map[doc.id] = doc.name

    sources: list[SourceItem] = []
    expanded_context = await expand_with_neighbors(selected_chunks, session)
    filtered_context: list[str] = list(expanded_context)
    for item in selected_chunks:
        chunk_text = item["text"]
        meta = item["metadata"]
        doc_id = meta.get("doc_id")
        doc_name = meta.get("doc_name") or doc_name_map.get(doc_id)
        page = meta.get("page")
        chunk_id = item["chunk_id"]
        quote = (chunk_text or "").strip().replace("\n", " ")
        if len(quote) > 240:
            quote = quote[:240].rstrip() + "..."
        if chunk_text not in filtered_context:
            filtered_context.append(chunk_text)
        sources.append(
            SourceItem(
                source_type="source",
                doc_id=doc_id,
                doc_name=doc_name,
                page=page,
                chunk_id=chunk_id,
                quote=quote or None,
            )
        )

    answer = await rag_service.generate_answer(
        query=normalized_question,
        context=filtered_context,
        chat_history=chat_history,
        language=language,
        model=model,
        assistant_name=profile.assistant_name,
        answer_rules=profile.answer_rules(language),
        no_data_answer=no_data_answer,
    )
    if is_no_data_answer(answer):
        sources = []
    log_entry = Log(
        question=chat_request.question,
        answer=answer,
        sources=json.dumps([item.model_dump() for item in sources], ensure_ascii=False),
        time_ms=int((perf_counter() - started) * 1000),
        user_id=current_user.id,
        notebook_id=notebook.id if notebook else None,
        domain_profile=profile.name,
    )
    session.add(log_entry)
    await session.commit()
    await session.refresh(log_entry)
    return ChatResponse(answer=answer, sources=sources, log_id=log_entry.id)
