from typing import List

from pydantic import BaseModel


class ChatRequest(BaseModel):
    question: str
    notebook_id: int | None = None
    domain_profile: str | None = None


class SourceItem(BaseModel):
    source_type: str | None = None
    doc_id: int | None = None
    doc_name: str | None = None
    page: int | None = None
    chunk_id: str | None = None
    category: str | None = None
    quote: str | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceItem]
    log_id: int
