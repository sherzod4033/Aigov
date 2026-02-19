import json
import os
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.api import deps
from app.models.models import User, Document, Chunk
from app.services.document_service import DocumentService
from app.services.hybrid_chunker import HybridChunker
from app.services.rag_service import RAGService

router = APIRouter()


@router.post("/upload", response_model=Document)
async def upload_document(
    file: UploadFile,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: AsyncSession = Depends(deps.get_session)
) -> Any:
    """
    Upload a document (PDF/DOCX/TXT).
    1. Save file locally
    2. Extract blocks & chunk (unified pipeline)
    3. Index in ChromaDB (batch)
    4. Save metadata in DB
    """
    try:
        file_ext = DocumentService.validate_upload_file(file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # 1. Save file
    file_path = await DocumentService.save_upload_file(file)

    # 2. Extract blocks & chunk (blocking I/O → threadpool)
    chunker = HybridChunker()
    chunk_results = await run_in_threadpool(
        DocumentService.extract_and_chunk, file_path, file_ext, chunker
    )

    if not chunk_results:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=400, detail="Could not extract text from file")

    sample_text = " ".join(cr.text for cr in chunk_results[:5])
    detected_language = DocumentService.detect_language(sample_text)

    # 3. Save Document Metadata
    actual_size = os.path.getsize(file_path)
    doc = Document(
        name=file.filename,
        path=file_path,
        size=actual_size,
        language=detected_language,
        status="indexed",
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    # 4. Save Chunks & Index in ChromaDB (batch)
    rag_service = RAGService()
    docs_text = []
    ids = []
    metadatas = []

    for cr in chunk_results:
        chunk = Chunk(
            text=cr.text,
            page=cr.page_start,
            chunk_index=cr.chunk_index,
            section=cr.section_path_json if cr.section_path else None,
            doc_id=doc.id,
        )
        session.add(chunk)
        await session.flush()  # get ID

        docs_text.append(chunk.text)
        ids.append(str(chunk.id))
        metadatas.append({
            "doc_id": doc.id,
            "doc_name": doc.name,
            "page": chunk.page,
            "chunk_index": cr.chunk_index,
        })

    await session.commit()

    # Index in Chroma (batch)
    try:
        rag_service.add_documents(docs_text, metadatas, ids)
    except Exception as exc:
        doc.status = "error"
        session.add(doc)
        await session.commit()
        raise HTTPException(
            status_code=503,
            detail="Document saved, but indexing failed: ChromaDB is unavailable.",
        ) from exc

    return doc


@router.get("/", response_model=List[Document])
async def read_documents(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(deps.get_session),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """Retrieve documents."""
    result = await session.exec(select(Document).offset(skip).limit(limit))
    return result.all()


@router.get("/{id}/chunks", response_model=List[Chunk])
async def get_document_chunks(
    id: int,
    session: AsyncSession = Depends(deps.get_session),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """Get all chunks for a specific document."""
    doc = await session.get(Document, id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    result = await session.exec(
        select(Chunk).where(Chunk.doc_id == id).order_by(Chunk.chunk_index)
    )
    return result.all()


@router.delete("/{id}", response_model=Document)
async def delete_document(
    id: int,
    session: AsyncSession = Depends(deps.get_session),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """Delete a document."""
    doc = await session.get(Document, id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks_result = await session.exec(select(Chunk).where(Chunk.doc_id == id))
    chunks = chunks_result.all()
    chunk_ids = [str(chunk.id) for chunk in chunks if chunk.id is not None]

    rag_service = RAGService()
    try:
        rag_service.delete_documents(chunk_ids)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Failed to delete embeddings from ChromaDB.",
        ) from exc

    if doc.path and os.path.exists(doc.path):
        try:
            os.remove(doc.path)
        except OSError as exc:
            raise HTTPException(
                status_code=500,
                detail="Failed to delete document file from disk.",
            ) from exc

    for chunk in chunks:
        await session.delete(chunk)
    await session.delete(doc)
    await session.commit()
    return doc


@router.post("/reindex")
async def reindex_all_documents(
    current_user: User = Depends(deps.get_current_active_superuser),
    session: AsyncSession = Depends(deps.get_session),
) -> Any:
    """
    Re-chunk and re-embed ALL documents using the new HybridChunker pipeline.
    1. Delete all chunks from DB and ChromaDB
    2. Re-extract and re-chunk each document
    3. Re-index in ChromaDB with new embeddings
    """
    import logging
    logger = logging.getLogger(__name__)

    result = await session.exec(select(Document))
    documents = result.all()
    if not documents:
        return {"status": "ok", "message": "No documents to reindex", "total_chunks": 0}

    rag_service = RAGService()
    chunker = HybridChunker()

    # Delete all existing chunks from ChromaDB
    all_chunks_result = await session.exec(select(Chunk))
    all_chunks = all_chunks_result.all()
    old_chunk_ids = [str(c.id) for c in all_chunks if c.id is not None]
    if old_chunk_ids:
        try:
            rag_service.delete_documents(old_chunk_ids)
        except Exception:
            logger.warning("Could not delete old chunks from ChromaDB")

    # Delete all chunks from DB
    for chunk in all_chunks:
        await session.delete(chunk)
    await session.flush()

    total_chunks = 0
    errors = []

    for doc in documents:
        try:
            if not doc.path or not os.path.exists(doc.path):
                errors.append(f"File missing for document {doc.id}: {doc.name}")
                doc.status = "error"
                session.add(doc)
                continue

            ext = DocumentService.get_extension(doc.name or doc.path)

            # Unified pipeline: extract blocks → chunk
            chunk_results = await run_in_threadpool(
                DocumentService.extract_and_chunk, doc.path, ext, chunker
            )

            if not chunk_results:
                errors.append(f"No text extracted from document {doc.id}: {doc.name}")
                doc.status = "error"
                session.add(doc)
                continue

            docs_text = []
            ids = []
            metadatas = []

            for cr in chunk_results:
                chunk = Chunk(
                    text=cr.text,
                    page=cr.page_start,
                    chunk_index=cr.chunk_index,
                    section=cr.section_path_json if cr.section_path else None,
                    doc_id=doc.id,
                )
                session.add(chunk)
                await session.flush()

                docs_text.append(chunk.text)
                ids.append(str(chunk.id))
                metadatas.append({
                    "doc_id": doc.id,
                    "doc_name": doc.name,
                    "page": chunk.page,
                    "chunk_index": cr.chunk_index,
                })

            # Batch index in Chroma
            rag_service.add_documents(docs_text, metadatas, ids)
            doc.status = "indexed"
            session.add(doc)
            total_chunks += len(chunk_results)
            logger.info(f"Reindexed doc {doc.id} ({doc.name}): {len(chunk_results)} chunks")

        except Exception as exc:
            errors.append(f"Error reindexing doc {doc.id} ({doc.name}): {str(exc)}")
            doc.status = "error"
            session.add(doc)

    await session.commit()
    return {
        "status": "ok" if not errors else "partial",
        "total_documents": len(documents),
        "total_chunks": total_chunks,
        "errors": errors,
    }
