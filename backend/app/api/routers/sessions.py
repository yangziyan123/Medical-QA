from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, delete, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.models.message import Message
from app.models.qa_run import QARun
from app.models.session import Session
from app.models.user import User
from app.schemas.message import MessageResponse
from app.schemas.session import (
    SessionCreateRequest,
    SessionListItem,
    SessionListResponse,
    SessionResponse,
    SessionUpdateRequest,
    SessionWithMessagesResponse,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _encode_cursor(updated_at: datetime, session_id: uuid.UUID) -> str:
    payload = {"updated_at": updated_at.isoformat(), "id": str(session_id)}
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
        updated_at = datetime.fromisoformat(payload["updated_at"])
        session_id = uuid.UUID(payload["id"])
        return updated_at, session_id
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cursor") from exc


@router.post("", response_model=SessionResponse)
async def create_session(
    payload: SessionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SessionResponse:
    session = Session(user_id=current_user.id, title=payload.title.strip() if payload.title else None)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return SessionResponse.model_validate(session)


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SessionListResponse:
    stmt = select(Session).where(Session.user_id == current_user.id)

    if cursor:
        cursor_updated_at, cursor_id = _decode_cursor(cursor)
        stmt = stmt.where(
            or_(
                Session.updated_at < cursor_updated_at,
                and_(Session.updated_at == cursor_updated_at, Session.id < cursor_id),
            )
        )

    stmt = stmt.order_by(desc(Session.updated_at), desc(Session.id)).limit(limit + 1)
    result = await db.execute(stmt)
    rows = list(result.scalars().all())

    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = _encode_cursor(last.updated_at, last.id)
        rows = rows[:limit]

    items = [SessionListItem.model_validate(s) for s in rows]
    return SessionListResponse(items=items, next_cursor=next_cursor)


@router.get("/{session_id}", response_model=SessionWithMessagesResponse)
async def get_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SessionWithMessagesResponse:
    session_result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == current_user.id)
    )
    session = session_result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    messages_result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.asc(), Message.id.asc())
    )
    messages = [MessageResponse.model_validate(m) for m in messages_result.scalars().all()]

    return SessionWithMessagesResponse(
        session=SessionResponse.model_validate(session),
        messages=messages,
    )


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: uuid.UUID,
    payload: SessionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SessionResponse:
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    title = payload.title.strip() if payload.title else None
    session.title = title
    session.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)
    return SessionResponse.model_validate(session)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # Delete in safe order to satisfy FK constraints:
    # qa_runs -> messages -> session
    await db.execute(delete(QARun).where(QARun.session_id == session.id))
    await db.execute(delete(Message).where(Message.session_id == session.id))
    await db.delete(session)
    await db.commit()
    return None
