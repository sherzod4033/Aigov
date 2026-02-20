import json
import logging
import math
import re
from time import perf_counter
from typing import Any, List
from fastapi import APIRouter, Depends, Request
from sqlmodel.ext.asyncio.session import AsyncSession
from pydantic import BaseModel
from sqlmodel import select

from app.api import deps
from app.core.rate_limit import chat_limiter, check_rate_limit
from app.models.models import User, Log, Document, Chunk
from app.services.rag_service import RAGService, RELEVANCE_DISTANCE_THRESHOLD
from app.services.runtime_settings_service import RuntimeSettingsService

logger = logging.getLogger(__name__)

router = APIRouter()

# Removed local RU_TJ_STOPWORDS and _stem_simple, using RAGService instead.


class ChatRequest(BaseModel):
    question: str

class SourceItem(BaseModel):
    source_type: str | None = None
    doc_id: int | None = None
    doc_name: str | None = None
    page: int | None = None
    chunk_id: str | None = None
    category: str | None = None
    quote: str | None = None

class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceItem]
    log_id: int


# Tokenization logic moved to RAGService.


def _safe_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def _is_no_data_answer(answer: str) -> bool:
    normalized = " ".join((answer or "").lower().split())
    return (
        "ответ не найден в базе" in normalized
        or "маълумот дар база мавҷуд нест" in normalized
    )


async def _expand_with_neighbors(
    selected_chunks: list[dict[str, Any]],
    session: AsyncSession,
) -> list[str]:
    """
    Neighbor expansion: for each selected chunk, fetch its adjacent chunks
    (chunk_index - 1 and chunk_index + 1) from the DB and add their text
    to the context. This provides seamless coverage across chunk boundaries
    without duplicating text in the embedding store.
    """
    if not selected_chunks:
        return []

    # Collect (doc_id, chunk_index) pairs for neighbor lookup
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

    # Fetch neighbors from DB in one query
    neighbor_texts: dict[str, str] = {}  # chunk_id -> text
    if neighbor_queries:
        from sqlalchemy import or_, and_
        conditions = [
            and_(Chunk.doc_id == did, Chunk.chunk_index == cidx)
            for did, cidx in neighbor_queries
        ]
        result = await session.exec(
            select(Chunk).where(or_(*conditions))
        )
        for chunk in result.all():
            cid = str(chunk.id)
            if cid not in seen_ids:
                neighbor_texts[cid] = chunk.text

    # Build expanded context: for each selected chunk, prepend/append neighbors
    expanded: list[str] = []
    for item in selected_chunks:
        expanded.append(item["text"])

    # Add unique neighbor texts at the end
    for text in neighbor_texts.values():
        expanded.append(text)

    return expanded

def _is_greeting(text: str) -> bool:
    lowered = text.lower()
    patterns = [
        r"\b(салом|привет|здравствуйте|добрый\s+(день|вечер|утро))\b",
    ]
    for pattern in patterns:
        if re.search(pattern, lowered):
            if len(lowered.split()) <= 3:
                return True
    return False


def _select_relevant_chunks(
    context: list[str],
    context_chunk_ids: list[str],
    context_metadatas: list[dict],
    context_distances: list[Any],
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
        distance = _safe_float(context_distances[idx] if idx < len(context_distances) else None)
        
        candidates.append(
            {
                "idx": idx,
                "text": chunk_text,
                "metadata": metadata,
                "chunk_id": context_chunk_ids[idx] if idx < len(context_chunk_ids) else None,
                "distance": distance,
            }
        )

    if not candidates:
        return []

    # Filter by semantic distance ONLY.
    # Distance <= 1.8 is considered "relevant" in this configuration.
    relevant = [item for item in candidates if item["distance"] is not None and item["distance"] <= RELEVANCE_DISTANCE_THRESHOLD]
    
    # Sort by closest distance
    relevant.sort(key=lambda x: x["distance"])
    
    return relevant[:5]

@router.post("/", response_model=ChatResponse)
async def chat(
    request: Request,
    chat_request: ChatRequest,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(deps.get_session)
) -> Any:
    """
    Chat with the AI.
    1. Search related chunks in ChromaDB
    2. Generate answer using Gemma + OpenAI
    3. Log the request
    
    Rate limited to 30 requests per minute per IP.
    """
    # Check rate limit
    await check_rate_limit(request, chat_limiter)
    
    started = perf_counter()
    rag_service = RAGService()
    normalized_question = rag_service.normalize_query(chat_request.question)
    language = rag_service.detect_language(normalized_question)
    runtime_settings = RuntimeSettingsService.get_settings()
    top_k = runtime_settings.get("top_k", 5)
    model = runtime_settings.get("model", "gemma3n:e4b")
    no_data_answer = (
        "Маълумот дар база мавҷуд нест / Ответ не найден в базе"
        if language == "tj"
        else "Ответ не найден в базе / Маълумот дар база мавҷуд нест"
    )

    if _is_greeting(chat_request.question):
        greeting_answer = (
            "Салом! Ман AndozAI, ёрдамчии шумо оид ба андоз. Ба ман савол диҳед."
            if language == "tj"
            else "Здравствуйте! Я AndozAI, ваш налоговый помощник. Задавайте вопросы."
        )
        empty_sources: List[SourceItem] = []
        log_entry = Log(
            question=chat_request.question,
            answer=greeting_answer,
            sources=json.dumps([item.model_dump() for item in empty_sources], ensure_ascii=False),
            time_ms=int((perf_counter() - started) * 1000),
            user_id=current_user.id,
        )
        session.add(log_entry)
        await session.commit()
        await session.refresh(log_entry)
        return ChatResponse(answer=greeting_answer, sources=empty_sources, log_id=log_entry.id)

    if rag_service.is_prompt_injection_attempt(normalized_question):
        safe_answer = (
            "Дархост рад шуд: савол дорои дастурҳои хатарнок аст. "
            "Лутфан саволи худро танҳо дар бораи мавзӯи андоз нависед."
            if language == "tj"
            else "Запрос отклонен: обнаружена попытка обойти системные правила. "
                 "Сформулируйте вопрос только по налоговой теме."
        )
        empty_sources: List[SourceItem] = []
        log_entry = Log(
            question=chat_request.question,
            answer=safe_answer,
            sources=json.dumps([item.model_dump() for item in empty_sources], ensure_ascii=False),
            time_ms=int((perf_counter() - started) * 1000),
            user_id=current_user.id,
        )
        session.add(log_entry)
        await session.commit()
        await session.refresh(log_entry)
        return ChatResponse(answer=safe_answer, sources=empty_sources, log_id=log_entry.id)

    # 0. Fetch Chat History
    history_result = await session.exec(
        select(Log)
        .where(Log.user_id == current_user.id)
        .order_by(Log.created_at.desc())
        .limit(5)
    )
    history_logs = sorted(history_result.all(), key=lambda x: x.created_at)
    # More robust mapping:
    chat_history = []
    for log in history_logs:
        chat_history.append({"role": "user", "content": log.question})
        chat_history.append({"role": "assistant", "content": log.answer})

    # 1. Condense Query for Search
    # Skip condensation for article-reference queries to prevent the LLM
    # from rewriting away the article number (e.g. "Моддаи 2" → "содержание закона").
    article_ref = rag_service._detect_article_reference(normalized_question)
    if article_ref:
        search_query = normalized_question
        logger.debug(f"Article reference detected ({article_ref}), skipping condensation")
    else:
        search_query = await rag_service.condense_query(normalized_question, chat_history, model=model)
        logger.debug(f"Condensed Search Query: {search_query}")

    # 2. Search
    logger.debug(f"Querying ChromaDB with: {search_query}, top_k={top_k}")
    results = rag_service.query_documents(search_query, n_results=top_k)
    documents = results.get("documents", [])
    chunk_ids = results.get("ids", [])
    metadatas = results.get("metadatas", [])
    distances = results.get("distances", [])
    
    logger.debug(f"ChromaDB results: {len(documents[0]) if documents else 0} documents")

    context = documents[0] if documents else []
    context_chunk_ids = chunk_ids[0] if chunk_ids else []
    context_metadatas = metadatas[0] if metadatas else []
    context_distances = distances[0] if distances else []
    
    logger.debug(f"Context: {len(context)} chunks, distances: {context_distances}")
    
    selected_chunks = _select_relevant_chunks(
        context=context,
        context_chunk_ids=context_chunk_ids,
        context_metadatas=context_metadatas,
        context_distances=context_distances,
    )

    # Cross-language fallback: map Tajik query terms to RU tax vocabulary
    # and retry retrieval when initial lookup returns no relevant context.
    if not selected_chunks and language == "tj":
        hinted_query = rag_service.tajik_query_to_russian_hint(search_query)
        if hinted_query and hinted_query != search_query:
            logger.debug(f"Retry ChromaDB with Tajik->RU hint: {hinted_query}")
            alt_results = rag_service.query_documents(hinted_query, n_results=top_k)
            alt_documents = alt_results.get("documents", [])
            alt_chunk_ids = alt_results.get("ids", [])
            alt_metadatas = alt_results.get("metadatas", [])
            alt_distances = alt_results.get("distances", [])

            alt_context = alt_documents[0] if alt_documents else []
            alt_context_chunk_ids = alt_chunk_ids[0] if alt_chunk_ids else []
            alt_context_metadatas = alt_metadatas[0] if alt_metadatas else []
            alt_context_distances = alt_distances[0] if alt_distances else []

            selected_chunks = _select_relevant_chunks(
                context=alt_context,
                context_chunk_ids=alt_context_chunk_ids,
                context_metadatas=alt_context_metadatas,
                context_distances=alt_context_distances,
            )
    
    logger.debug(f"Selected chunks: {len(selected_chunks)}")
    for chunk in selected_chunks:
        logger.debug(f"  - chunk_id={chunk.get('chunk_id')}, overlap={chunk.get('overlap')}")

    has_context = bool(selected_chunks)

    if not has_context:
        logger.warning(f"No relevant context found for query: {search_query}")
        answer_text = no_data_answer
        empty_sources: List[SourceItem] = []
        log_entry = Log(
            question=chat_request.question,
            answer=answer_text,
            sources=json.dumps([item.model_dump() for item in empty_sources], ensure_ascii=False),
            time_ms=int((perf_counter() - started) * 1000),
            user_id=current_user.id
        )
        session.add(log_entry)
        await session.commit()
        await session.refresh(log_entry)
        
        return ChatResponse(answer=answer_text, sources=empty_sources, log_id=log_entry.id)

    doc_id_set = {
        item["metadata"].get("doc_id")
        for item in selected_chunks
        if item["metadata"].get("doc_id") is not None
    }
    doc_name_map = {}
    if doc_id_set:
        docs_result = await session.exec(select(Document).where(Document.id.in_(doc_id_set)))
        for doc in docs_result.all():
            doc_name_map[doc.id] = doc.name

    sources: List[SourceItem] = []
    # Neighbor expansion: fetch adjacent chunks from DB for richer context
    expanded_context = await _expand_with_neighbors(selected_chunks, session)

    filtered_context: List[str] = list(expanded_context)
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
        # chunk_text already in filtered_context via neighbor expansion
        if chunk_text not in filtered_context:
            filtered_context.append(chunk_text)
        sources.append(
            SourceItem(
                source_type="document",
                doc_id=doc_id,
                doc_name=doc_name,
                page=page,
                chunk_id=chunk_id,
                quote=quote or None,
            )
        )
    
    # 3. Generate
    answer = await rag_service.generate_answer(
        query=normalized_question,
        context=filtered_context,
        chat_history=chat_history,
        language=language,
        model=model,
    )

    if _is_no_data_answer(answer):
        sources = []
    
    # 3. Log
    log_entry = Log(
        question=chat_request.question,
        answer=answer,
        sources=json.dumps([item.model_dump() for item in sources], ensure_ascii=False),
        time_ms=int((perf_counter() - started) * 1000),
        user_id=current_user.id
    )
    session.add(log_entry)
    await session.commit()
    await session.refresh(log_entry)
    
    return ChatResponse(
        answer=answer,
        sources=sources,
        log_id=log_entry.id
    )
