import json
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.models import Job


class JobsService:
    @staticmethod
    async def enqueue(
        session: AsyncSession,
        job_type: str,
        payload: dict[str, Any] | None = None,
        *,
        source_id: int | None = None,
        notebook_id: int | None = None,
        created_by: int | None = None,
    ) -> Job:
        job = Job(
            job_type=job_type,
            status="queued",
            payload_json=json.dumps(payload or {}, ensure_ascii=False),
            source_id=source_id,
            notebook_id=notebook_id,
            created_by=created_by,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job

    @staticmethod
    async def list_jobs(session: AsyncSession, limit: int = 100) -> list[Job]:
        result = await session.exec(
            select(Job).order_by(Job.created_at.desc()).limit(limit)
        )
        return result.all()

    @staticmethod
    async def mark_running(session: AsyncSession, job: Job) -> Job:
        job.status = "running"
        job.attempt_count += 1
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job

    @staticmethod
    async def mark_finished(
        session: AsyncSession,
        job: Job,
        *,
        result: dict[str, Any] | None = None,
        error_text: str | None = None,
    ) -> Job:
        job.status = "failed" if error_text else "completed"
        job.result_json = (
            json.dumps(result or {}, ensure_ascii=False) if result is not None else None
        )
        job.error_text = error_text
        job.progress = 100
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job
