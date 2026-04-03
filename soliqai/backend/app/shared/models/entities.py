from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class NotebookBase(SQLModel):
    name: str = Field(index=True)
    description: Optional[str] = None
    domain_profile: str = Field(default="tax", index=True)


class Notebook(NotebookBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: Optional[int] = Field(default=None, foreign_key="user.id", nullable=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserBase(SQLModel):
    username: str = Field(index=True, unique=True)
    role: str = Field(default="user")


class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    password_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentBase(SQLModel):
    name: str = Field(index=True)
    path: str
    size: int
    language: str = Field(default="ru")
    status: str = Field(default="pending")


class Document(DocumentBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    notebook_id: Optional[int] = Field(
        default=None, foreign_key="notebook.id", nullable=True, index=True
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ChunkBase(SQLModel):
    text: str
    page: int
    chunk_index: Optional[int] = None
    section: Optional[str] = None
    embedding_id: Optional[str] = None


class Chunk(ChunkBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    doc_id: int = Field(foreign_key="document.id", ondelete="CASCADE")


class LogBase(SQLModel):
    question: str
    answer: str
    sources: Optional[str] = None
    time_ms: int
    rating: Optional[str] = None


class Log(LogBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(foreign_key="user.id", nullable=True)
    notebook_id: Optional[int] = Field(
        default=None, foreign_key="notebook.id", nullable=True, index=True
    )
    domain_profile: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class NoteBase(SQLModel):
    title: str = Field(index=True)
    body: str = ""
    kind: str = Field(default="manual")
    status: str = Field(default="active")


class Note(NoteBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    notebook_id: int = Field(foreign_key="notebook.id", index=True)
    created_by: Optional[int] = Field(
        default=None, foreign_key="user.id", nullable=True
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class InsightBase(SQLModel):
    title: str = Field(index=True)
    body: str = ""
    insight_type: str = Field(default="summary")
    evidence_json: Optional[str] = None


class Insight(InsightBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    notebook_id: int = Field(foreign_key="notebook.id", index=True)
    note_id: Optional[int] = Field(default=None, foreign_key="note.id", nullable=True)
    created_by: Optional[int] = Field(
        default=None, foreign_key="user.id", nullable=True
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class JobBase(SQLModel):
    job_type: str = Field(index=True)
    status: str = Field(default="queued", index=True)
    payload_json: Optional[str] = None
    result_json: Optional[str] = None
    error_text: Optional[str] = None
    progress: int = Field(default=0)
    attempt_count: int = Field(default=0)


class Job(JobBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: Optional[int] = Field(
        default=None, foreign_key="document.id", nullable=True, index=True
    )
    notebook_id: Optional[int] = Field(
        default=None, foreign_key="notebook.id", nullable=True, index=True
    )
    created_by: Optional[int] = Field(
        default=None, foreign_key="user.id", nullable=True
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
