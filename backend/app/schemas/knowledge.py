from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class KnowledgeImportRequest(BaseModel):
    source_type: str = Field(default="raw_text", max_length=32)
    title: str = Field(min_length=1, max_length=255)
    version: str | None = Field(default=None, max_length=64)
    source_url: str | None = None
    raw_text: str = Field(min_length=1, max_length=2_000_000)


class KnowledgeImportResponse(BaseModel):
    document_id: uuid.UUID
    chunk_count: int


class KnowledgeSearchItem(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    title: str
    version: str | None
    source_url: str | None
    chunk_index: int
    score: float
    text: str


class KnowledgeSearchResponse(BaseModel):
    items: list[KnowledgeSearchItem]

