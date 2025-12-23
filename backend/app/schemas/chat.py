from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class ChatAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    session_id: uuid.UUID | None = None
    client_msg_id: str | None = Field(default=None, max_length=64)


class Citation(BaseModel):
    chunk_id: uuid.UUID
    document: dict[str, Any] | None = None
    snippet: str | None = None
    score: float | None = None


class SafetyInfo(BaseModel):
    disclaimer: str
    triage: str = "normal"


class ChatAskResponse(BaseModel):
    session_id: uuid.UUID
    qa_run_id: uuid.UUID
    answer: str
    citations: list[Citation] = []
    safety: SafetyInfo

