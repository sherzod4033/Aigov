from typing import Any, List, Optional
from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from pydantic import BaseModel
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
    current_user: User = Depends(deps.get_current_active_superuser),
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
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    return await DocumentModuleService.read_documents(
        session=session, skip=skip, limit=limit, notebook_id=notebook_id
    )


@router.post("/attach", response_model=AttachSourcesResponse)
async def attach_documents(
    payload: AttachSourcesPayload,
    current_user: User = Depends(deps.get_current_active_superuser),
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
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    return await DocumentModuleService.get_document_chunks(
        session=session, document_id=id
    )


@router.delete("/{id}", response_model=Document)
async def delete_document(
    id: int,
    session: AsyncSession = Depends(deps.get_session),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    return await DocumentModuleService.delete_document(session=session, document_id=id)


@router.post("/reindex")
async def reindex_all_documents(
    current_user: User = Depends(deps.get_current_active_superuser),
    session: AsyncSession = Depends(deps.get_session),
) -> Any:
    return await DocumentModuleService.reindex_all_documents(session=session)
