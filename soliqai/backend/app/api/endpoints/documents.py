import os
from typing import List, Any
from fastapi import APIRouter, Depends, UploadFile, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.api import deps
from app.models.models import User, Document, Chunk
from app.services.document_service import DocumentService
from app.services.ocr_service import OCRService
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
    2. Extract text (OCR if needed)
    3. Index in ChromaDB
    4. Save metadata in DB
    """
    try:
        file_ext = DocumentService.validate_upload_file(file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # 1. Save file
    file_path = await DocumentService.save_upload_file(file)

    # 2. Extract text
    if file_ext == ".pdf" and DocumentService.is_scanned_pdf(file_path):
        ocr_pages = OCRService.extract_text_from_scanned_pdf(file_path)
        chunks_data = []
        for page_data in ocr_pages:
            chunks_data.extend(
                DocumentService.semantic_chunk_text(
                    page_data.get("text", ""),
                    page=page_data.get("page", 1),
                )
            )
    else:
        chunks_data = DocumentService.extract_chunks(file_path, file_ext)

    if not chunks_data:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=400, detail="Could not extract text from file")

    sample_text = " ".join(chunk.get("text", "") for chunk in chunks_data[:5])
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

    # 4. Save Chunks & Index in ChromaDB
    rag_service = RAGService()
    docs_text = []
    ids = []
    metadatas = []

    for i, chunk_data in enumerate(chunks_data):
        chunk = Chunk(
            text=chunk_data["text"],
            page=chunk_data["page"],
            doc_id=doc.id
        )
        session.add(chunk)
        await session.flush() # get ID
        
        docs_text.append(chunk.text)
        ids.append(str(chunk.id))
        metadatas.append({"doc_id": doc.id, "doc_name": doc.name, "page": chunk.page})

    await session.commit()
    
    # Index in Chroma
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
    """
    Retrieve documents.
    """
    result = await session.exec(select(Document).offset(skip).limit(limit))
    return result.all()

@router.get("/{id}/chunks", response_model=List[Chunk])
async def get_document_chunks(
    id: int,
    session: AsyncSession = Depends(deps.get_session),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Get all chunks for a specific document.
    """
    doc = await session.get(Document, id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    result = await session.exec(select(Chunk).where(Chunk.doc_id == id).order_by(Chunk.page))
    return result.all()


@router.delete("/{id}", response_model=Document)
async def delete_document(
    id: int,
    session: AsyncSession = Depends(deps.get_session),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Delete a document.
    """
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
