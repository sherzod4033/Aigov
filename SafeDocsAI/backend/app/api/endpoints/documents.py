import os
from typing import Any, List, Optional
from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api import deps
from app.models.models import User, Document, Chunk
from app.modules.documents import DocumentModuleService

router = APIRouter()


class AttachSourcesPayload(BaseModel):
    notebook_id: int
    source_ids: list[int]


class AttachSourcesResponse(BaseModel):
    updated_count: int
    documents: list[Document]


@router.post("/upload", response_model=Document)
async def upload_document(
    file: UploadFile,
    notebook_id: Optional[int] = Form(default=None),
    current_user: User = Depends(deps.get_current_content_manager_or_admin),
    session: AsyncSession = Depends(deps.get_session),
) -> Any:
    return await DocumentModuleService.upload_document(
        session=session, file=file, notebook_id=notebook_id
    )


@router.get("/", response_model=List[Document])
async def read_documents(
    skip: int = 0,
    limit: int = 100,
    notebook_id: int | None = Query(default=None),
    session: AsyncSession = Depends(deps.get_session),
    current_user: User = Depends(deps.get_current_content_manager_or_admin),
) -> Any:
    return await DocumentModuleService.read_documents(
        session=session, skip=skip, limit=limit, notebook_id=notebook_id
    )


@router.post("/attach", response_model=AttachSourcesResponse)
async def attach_documents(
    payload: AttachSourcesPayload,
    current_user: User = Depends(deps.get_current_content_manager_or_admin),
    session: AsyncSession = Depends(deps.get_session),
) -> Any:
    if not payload.source_ids:
        raise HTTPException(status_code=400, detail="No source ids provided")

    documents = await DocumentModuleService.attach_documents_to_notebook(
        session=session,
        notebook_id=payload.notebook_id,
        source_ids=payload.source_ids,
    )
    return AttachSourcesResponse(updated_count=len(documents), documents=documents)


@router.get("/{id}/chunks", response_model=List[Chunk])
async def get_document_chunks(
    id: int,
    session: AsyncSession = Depends(deps.get_session),
    current_user: User = Depends(deps.get_current_content_manager_or_admin),
) -> Any:
    return await DocumentModuleService.get_document_chunks(
        session=session, document_id=id
    )


@router.delete("/{id}", response_model=Document)
async def delete_document(
    id: int,
    session: AsyncSession = Depends(deps.get_session),
    current_user: User = Depends(deps.get_current_content_manager_or_admin),
) -> Any:
    return await DocumentModuleService.delete_document(session=session, document_id=id)


@router.post("/reindex")
async def reindex_all_documents(
    current_user: User = Depends(deps.get_current_active_superuser),
    session: AsyncSession = Depends(deps.get_session),
) -> Any:
    return await DocumentModuleService.reindex_all_documents(session=session)


MIME_MAP = {
    ".pdf": "application/pdf",
    ".txt": "text/plain; charset=utf-8",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.get("/{id}/preview")
async def preview_document(
    id: int,
    session: AsyncSession = Depends(deps.get_session),
    current_user: User = Depends(deps.get_current_user),
) -> FileResponse:
    doc = await session.get(Document, id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not doc.path or not os.path.exists(doc.path):
        raise HTTPException(status_code=404, detail="File not found on disk")
    ext = os.path.splitext(doc.name or doc.path)[1].lower()
    media_type = MIME_MAP.get(ext, "application/octet-stream")
    return FileResponse(
        doc.path,
        media_type=media_type,
        filename=doc.name,
    )


class ChunkContext(BaseModel):
    chunk_id: int
    text: str
    page: int
    chunk_index: int | None = None
    section: str | None = None
    doc_id: int
    doc_name: str
    highlight: bool = False


@router.get("/{id}/chunk/{chunk_id}/context")
async def get_chunk_context(
    id: int,
    chunk_id: int,
    neighbors: int = Query(default=2, ge=0, le=5),
    session: AsyncSession = Depends(deps.get_session),
    current_user: User = Depends(deps.get_current_user),
) -> list[ChunkContext]:
    """Return the target chunk plus neighboring chunks for context."""
    doc = await session.get(Document, id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    target = await session.get(Chunk, chunk_id)
    if not target or target.doc_id != id:
        raise HTTPException(status_code=404, detail="Chunk not found")

    result = await session.exec(
        select(Chunk)
        .where(Chunk.doc_id == id)
        .order_by(Chunk.page, Chunk.id)
    )
    all_chunks = result.all()

    target_idx = next(
        (i for i, c in enumerate(all_chunks) if c.id == chunk_id), None
    )
    if target_idx is None:
        raise HTTPException(status_code=404, detail="Chunk not found in document")

    start = max(0, target_idx - neighbors)
    end = min(len(all_chunks), target_idx + neighbors + 1)

    return [
        ChunkContext(
            chunk_id=c.id,
            text=c.text,
            page=c.page,
            chunk_index=c.chunk_index,
            section=c.section,
            doc_id=id,
            doc_name=doc.name,
            highlight=(c.id == chunk_id),
        )
        for c in all_chunks[start:end]
    ]
