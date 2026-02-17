from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy import or_

from app.api import deps
from app.core.database import get_session
from app.models.models import FAQ, User

router = APIRouter()

class FAQCreate(BaseModel):
    question: str
    answer: str
    category: str | None = None
    priority: int = 0

class FAQUpdate(BaseModel):
    question: str | None = None
    answer: str | None = None
    category: str | None = None
    priority: int | None = None

@router.get("/", response_model=List[FAQ])
async def read_faqs(
    skip: int = 0,
    limit: int = 100,
    q: str | None = None,
    category: str | None = None,
    session: AsyncSession = Depends(get_session)
) -> Any:
    statement = select(FAQ)
    if q:
        search = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                FAQ.question.ilike(search),
                FAQ.answer.ilike(search),
                FAQ.category.ilike(search),
            )
        )
    if category:
        statement = statement.where(FAQ.category == category)

    statement = statement.offset(skip).limit(limit)
    result = await session.exec(statement)
    return result.all()


@router.get("/categories", response_model=List[str])
async def read_categories(
    session: AsyncSession = Depends(get_session)
) -> Any:
    result = await session.exec(select(FAQ.category).where(FAQ.category.is_not(None)))
    categories = sorted({category for category in result.all() if category})
    return categories

@router.post("/", response_model=FAQ)
async def create_faq(
    faq_in: FAQCreate,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: AsyncSession = Depends(get_session)
) -> Any:
    faq = FAQ.model_validate(faq_in)
    session.add(faq)
    await session.commit()
    await session.refresh(faq)
    return faq

@router.put("/{faq_id}", response_model=FAQ)
async def update_faq(
    faq_id: int,
    faq_in: FAQUpdate,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: AsyncSession = Depends(get_session)
) -> Any:
    faq = await session.get(FAQ, faq_id)
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")
    
    faq_data = faq_in.model_dump(exclude_unset=True)
    for key, value in faq_data.items():
        setattr(faq, key, value)
    
    faq.updated_at = datetime.utcnow()
    session.add(faq)
    await session.commit()
    await session.refresh(faq)
    return faq

@router.delete("/{faq_id}", response_model=FAQ)
async def delete_faq(
    faq_id: int,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: AsyncSession = Depends(get_session)
) -> Any:
    faq = await session.get(FAQ, faq_id)
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")
    
    await session.delete(faq)
    await session.commit()
    return faq
