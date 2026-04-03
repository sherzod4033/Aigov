from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.models import Note


class NotesService:
    @staticmethod
    async def list_notes(
        session: AsyncSession, notebook_id: int | None = None
    ) -> list[Note]:
        statement = select(Note).order_by(Note.updated_at.desc())
        if notebook_id is not None:
            statement = statement.where(Note.notebook_id == notebook_id)
        result = await session.exec(statement)
        return result.all()
