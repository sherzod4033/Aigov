import json
from time import perf_counter

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.models import Document, Log, Notebook, User
from app.modules.ask.schemas import AskRequest, AskResponse, CitationItem
from app.modules.chat.service import (
    expand_with_neighbors,
    is_greeting,
    is_no_data_answer,
    resolve_retrieval_limits,
    run_retrieval,
)
from app.modules.rag.constants import DEFAULT_CHAT_MODEL
from app.services.profile_resolver import resolve_profile
from app.services.rag_service import RAGService
from app.services.runtime_settings_service import RuntimeSettingsService


async def handle_ask_request(
    ask_request: AskRequest,
    current_user: User,
    session: AsyncSession,
) -> AskResponse:
    started = perf_counter()
    rag_service = RAGService()
    normalized_question = rag_service.normalize_query(ask_request.question)
    language = rag_service.detect_language(normalized_question)
    runtime_settings = RuntimeSettingsService.get_settings()
    retrieval_top_k, top_k = resolve_retrieval_limits(
        runtime_settings,
        requested_top_k=ask_request.top_k,
    )
    model = runtime_settings.get("chat_model") or runtime_settings.get(
        "model", DEFAULT_CHAT_MODEL
    )

    notebook: Notebook | None = None
    if ask_request.notebook_id is not None:
        notebook = await session.get(Notebook, ask_request.notebook_id)
    if notebook is None:
        notebook_result = await session.exec(
            select(Notebook).order_by(Notebook.created_at.asc()).limit(1)
        )
        notebook = notebook_result.first()

    profile = resolve_profile(notebook=notebook, requested=ask_request.domain_profile)
    no_data_answer = profile.no_data_answer(language)

    if is_greeting(ask_request.question):
        answer = profile.greeting(language)
        log_entry = Log(
            question=ask_request.question,
            answer=answer,
            sources="[]",
            time_ms=int((perf_counter() - started) * 1000),
            user_id=current_user.id,
            notebook_id=notebook.id if notebook else None,
            domain_profile=profile.name,
        )
        session.add(log_entry)
        await session.commit()
        await session.refresh(log_entry)
        return AskResponse(answer=answer, citations=[], log_id=log_entry.id)

    if rag_service.is_prompt_injection_attempt(normalized_question):
        answer = profile.prompt_injection_message(language)
        log_entry = Log(
            question=ask_request.question,
            answer=answer,
            sources="[]",
            time_ms=int((perf_counter() - started) * 1000),
            user_id=current_user.id,
            notebook_id=notebook.id if notebook else None,
            domain_profile=profile.name,
        )
        session.add(log_entry)
        await session.commit()
        await session.refresh(log_entry)
        return AskResponse(answer=answer, citations=[], log_id=log_entry.id)

    article_ref = rag_service._detect_article_reference(normalized_question)
    search_query = normalized_question if article_ref else normalized_question

    allowed_doc_ids: set[int] | None = None
    if notebook and notebook.id is not None:
        notebook_docs_result = await session.exec(
            select(Document.id).where(Document.notebook_id == notebook.id)
        )
        allowed_doc_ids = {
            doc_id for doc_id in notebook_docs_result.all() if doc_id is not None
        }

    selected_chunks: list[dict] = []
    selected_chunks = await run_retrieval(
        rag_service=rag_service,
        session=session,
        profile=profile,
        language=language,
        search_query=search_query,
        allowed_doc_ids=allowed_doc_ids,
        retrieval_top_k=retrieval_top_k,
        final_top_k=top_k,
    )

    if not selected_chunks:
        answer = no_data_answer
        log_entry = Log(
            question=ask_request.question,
            answer=answer,
            sources="[]",
            time_ms=int((perf_counter() - started) * 1000),
            user_id=current_user.id,
            notebook_id=notebook.id if notebook else None,
            domain_profile=profile.name,
        )
        session.add(log_entry)
        await session.commit()
        await session.refresh(log_entry)
        return AskResponse(answer=answer, citations=[], log_id=log_entry.id)

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

    expanded_context = await expand_with_neighbors(selected_chunks, session)
    filtered_context = list(expanded_context)
    citations: list[CitationItem] = []
    for item in selected_chunks:
        chunk_text = item["text"]
        meta = item["metadata"]
        source_id = meta.get("doc_id")
        source_name = meta.get("doc_name") or doc_name_map.get(source_id)
        page = meta.get("page")
        chunk_id = item["chunk_id"]
        quote = (chunk_text or "").strip().replace("\n", " ")
        if len(quote) > 240:
            quote = quote[:240].rstrip() + "..."
        if chunk_text not in filtered_context:
            filtered_context.append(chunk_text)
        citations.append(
            CitationItem(
                source_id=source_id,
                source_name=source_name,
                page=page,
                chunk_id=chunk_id,
                quote=quote or None,
            )
        )

    answer = await rag_service.generate_answer(
        query=normalized_question,
        context=filtered_context,
        chat_history=[],
        language=language,
        model=model,
        assistant_name=profile.assistant_name,
        answer_rules=profile.answer_rules(language),
        no_data_answer=no_data_answer,
    )
    if is_no_data_answer(answer):
        citations = []

    log_entry = Log(
        question=ask_request.question,
        answer=answer,
        sources=json.dumps(
            [item.model_dump() for item in citations], ensure_ascii=False
        ),
        time_ms=int((perf_counter() - started) * 1000),
        user_id=current_user.id,
        notebook_id=notebook.id if notebook else None,
        domain_profile=profile.name,
    )
    session.add(log_entry)
    await session.commit()
    await session.refresh(log_entry)
    return AskResponse(answer=answer, citations=citations, log_id=log_entry.id)
