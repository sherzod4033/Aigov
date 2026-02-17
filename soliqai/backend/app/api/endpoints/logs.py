from datetime import datetime, date, time
from typing import List, Any, Literal
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select, desc
from sqlmodel.ext.asyncio.session import AsyncSession
from pydantic import BaseModel

from app.api import deps
from app.core.database import get_session
from app.models.models import Log, User, FAQ

router = APIRouter()

class RatingUpdate(BaseModel):
    rating: Literal["up", "down"]

class LogAnalytics(BaseModel):
    total_logs: int
    ups: int
    downs: int


class AddToFAQRequest(BaseModel):
    question: str | None = None
    answer: str | None = None
    category: str | None = None
    priority: int = 0


@router.get("/", response_model=List[Log])
async def read_logs(
    skip: int = 0,
    limit: int = 100,
    start_date: date | None = None,
    end_date: date | None = None,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: AsyncSession = Depends(get_session)
) -> Any:
    statement = select(Log)
    if start_date:
        statement = statement.where(Log.created_at >= datetime.combine(start_date, time.min))
    if end_date:
        statement = statement.where(Log.created_at <= datetime.combine(end_date, time.max))
    statement = statement.order_by(desc(Log.created_at)).offset(skip).limit(limit)

    result = await session.exec(statement)
    return result.all()

@router.post("/{log_id}/rating", response_model=Log)
async def rate_log(
    log_id: int,
    rating_in: RatingUpdate,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_session)
) -> Any:
    log = await session.get(Log, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    
    log.rating = rating_in.rating
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log

@router.get("/analytics", response_model=LogAnalytics)
async def get_analytics(
    current_user: User = Depends(deps.get_current_active_superuser),
    session: AsyncSession = Depends(get_session)
) -> Any:
    total = await session.exec(select(Log))
    total_logs = len(total.all())
    
    ups = await session.exec(select(Log).where(Log.rating == "up"))
    ups_count = len(ups.all())
    
    downs = await session.exec(select(Log).where(Log.rating == "down"))
    downs_count = len(downs.all())
    
    return LogAnalytics(
        total_logs=total_logs,
        ups=ups_count,
        downs=downs_count
    )


@router.post("/{log_id}/to-faq", response_model=FAQ)
async def add_log_to_faq(
    log_id: int,
    payload: AddToFAQRequest,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: AsyncSession = Depends(get_session),
) -> Any:
    log_entry = await session.get(Log, log_id)
    if not log_entry:
        raise HTTPException(status_code=404, detail="Log not found")

    question = (payload.question or log_entry.question or "").strip()
    answer = (payload.answer or log_entry.answer or "").strip()
    if not question or not answer:
        raise HTTPException(status_code=400, detail="Question and answer are required")

    faq = FAQ(
        question=question,
        answer=answer,
        category=payload.category,
        priority=payload.priority,
    )
    session.add(faq)
    await session.commit()
    await session.refresh(faq)
    return faq
