from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.message import MessageResponse


class SessionCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class SessionUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class SessionListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    updated_at: datetime


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class SessionWithMessagesResponse(BaseModel):
    session: SessionResponse
    messages: list[MessageResponse]


class SessionListResponse(BaseModel):
    items: list[SessionListItem]
    next_cursor: str | None = None
