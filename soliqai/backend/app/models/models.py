from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field

class UserBase(SQLModel):
    username: str = Field(index=True, unique=True)
    role: str = Field(default="user")  # 'admin' or 'content_manager'

class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    password_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class DocumentBase(SQLModel):
    name: str = Field(index=True)
    path: str
    size: int
    language: str = Field(default="ru")  # 'ru' or 'tj'
    status: str = Field(default="pending") # 'pending', 'indexed', 'error'

class Document(DocumentBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ChunkBase(SQLModel):
    text: str
    page: int
    section: Optional[str] = None
    embedding_id: Optional[str] = None # ChromaDB ID

class Chunk(ChunkBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    doc_id: int = Field(foreign_key="document.id", ondelete="CASCADE")

class LogBase(SQLModel):
    question: str
    answer: str
    sources: Optional[str] = None # JSON string of sources
    time_ms: int
    rating: Optional[str] = None # 'up', 'down'

class Log(LogBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(foreign_key="user.id", nullable=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
