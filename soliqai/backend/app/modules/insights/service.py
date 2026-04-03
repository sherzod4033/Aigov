from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.models import Insight


class InsightsService:
    @staticmethod
    async def list_insights(
        session: AsyncSession, notebook_id: int | None = None
    ) -> list[Insight]:
        statement = select(Insight).order_by(Insight.updated_at.desc())
        if notebook_id is not None:
            statement = statement.where(Insight.notebook_id == notebook_id)
        result = await session.exec(statement)
        return result.all()
