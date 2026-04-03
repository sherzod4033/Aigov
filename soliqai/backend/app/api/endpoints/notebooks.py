from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api import deps
from app.domain_profiles import list_domain_profiles
from app.shared.models import Notebook, User

router = APIRouter()


class NotebookCreate(BaseModel):
    name: str
    description: str | None = None
    domain_profile: str = "general"


class NotebookResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    domain_profile: str
    owner_id: int | None = None
    created_at: datetime


@router.get("/", response_model=list[NotebookResponse])
async def list_notebooks(
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(deps.get_session),
) -> Any:
    result = await session.exec(select(Notebook).order_by(Notebook.created_at.desc()))
    notebooks = result.all()
    return [
        NotebookResponse(
            id=notebook.id,
            name=notebook.name,
            description=notebook.description,
            domain_profile=notebook.domain_profile,
            owner_id=notebook.owner_id,
            created_at=notebook.created_at,
        )
        for notebook in notebooks
        if notebook.id is not None
    ]


@router.get("/{notebook_id}", response_model=NotebookResponse)
async def get_notebook(
    notebook_id: int,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(deps.get_session),
) -> Any:
    notebook = await session.get(Notebook, notebook_id)
    if not notebook or notebook.id is None:
        raise HTTPException(status_code=404, detail="Notebook not found")

    return NotebookResponse(
        id=notebook.id,
        name=notebook.name,
        description=notebook.description,
        domain_profile=notebook.domain_profile,
        owner_id=notebook.owner_id,
        created_at=notebook.created_at,
    )


@router.post("/", response_model=NotebookResponse)
async def create_notebook(
    payload: NotebookCreate,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(deps.get_session),
) -> Any:
    if payload.domain_profile not in list_domain_profiles():
        raise HTTPException(status_code=400, detail="Unsupported domain profile")

    notebook = Notebook(
        name=payload.name.strip(),
        description=payload.description,
        domain_profile=payload.domain_profile,
        owner_id=current_user.id,
    )
    session.add(notebook)
    await session.commit()
    await session.refresh(notebook)
    return NotebookResponse(
        id=notebook.id,
        name=notebook.name,
        description=notebook.description,
        domain_profile=notebook.domain_profile,
        owner_id=notebook.owner_id,
        created_at=notebook.created_at,
    )
