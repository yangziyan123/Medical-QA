from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
import httpx
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_flexible
from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.message import Message
from app.models.qa_run import QARun
from app.models.session import Session
from app.models.user import User
from app.schemas.chat import ChatAskRequest, ChatAskResponse, SafetyInfo
from app.rag.retriever import build_context, retrieve_chunks
from app.services.llm_client import get_llm_client

router = APIRouter(prefix="/api/chat", tags=["chat"])

_DISCLAIMER = "仅供参考，不能替代专业医疗建议。"


@router.post("/ask", response_model=ChatAskResponse)
async def ask(
    payload: ChatAskRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ChatAskResponse:
    settings = get_settings()
    now = datetime.now(timezone.utc)

    if payload.session_id is None:
        title = payload.question.strip()
        title = title[:50] if title else None
        session = Session(user_id=current_user.id, title=title)
        db.add(session)
        await db.flush()
    else:
        session_result = await db.execute(
            select(Session).where(Session.id == payload.session_id, Session.user_id == current_user.id)
        )
        session = session_result.scalar_one_or_none()
        if session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    try:
        retrieved = await retrieve_chunks(db, query=payload.question, top_k=settings.rag_top_k)
    except (RuntimeError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"RAG retrieval failed: {exc}") from exc
    context = build_context(retrieved) if retrieved else None

    user_message = Message(
        session_id=session.id,
        role="user",
        content=payload.question,
        client_msg_id=payload.client_msg_id,
    )
    db.add(user_message)
    await db.flush()

    start = time.perf_counter()
    llm = get_llm_client()
    try:
        llm_result = await llm.generate(question=payload.question, context=context)
    except (RuntimeError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"LLM failed: {exc}") from exc
    latency_ms = int((time.perf_counter() - start) * 1000)

    assistant_message = Message(
        session_id=session.id,
        role="assistant",
        content=llm_result.text,
    )
    db.add(assistant_message)
    await db.flush()

    citations = [
        {
            "chunk_id": str(c.chunk_id),
            "document": {"title": c.title, "version": c.version, "source_url": c.source_url},
            "snippet": c.text[:240],
            "score": c.score,
        }
        for c in retrieved
    ]

    prompt = None
    if context:
        prompt = (
            "你是医疗问答助手。回答需谨慎、避免诊断与处方，必要时建议就医。\n"
            f"用户问题：{payload.question}\n\n"
            f"参考资料（带引用编号）：\n{context}\n"
        )

    qa_run = QARun(
        session_id=session.id,
        user_message_id=user_message.id,
        assistant_message_id=assistant_message.id,
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model or None,
        prompt_version="v1",
        prompt=prompt,
        answer=llm_result.text,
        citations=citations,
        latency_ms=latency_ms,
        safety_flags={"disclaimer": _DISCLAIMER, "triage": "normal"},
    )
    db.add(qa_run)

    session.updated_at = now
    await db.commit()

    return ChatAskResponse(
        session_id=session.id,
        qa_run_id=qa_run.id,
        answer=llm_result.text,
        citations=citations,
        safety=SafetyInfo(disclaimer=_DISCLAIMER, triage="normal"),
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n\n"


async def _read_json_body(request: Request) -> dict:
    body = await request.body()
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty body")

    try:
        value = json.loads(body)
    except UnicodeDecodeError:
        for encoding in ("utf-8-sig", "gbk"):
            try:
                value = json.loads(body.decode(encoding))
                break
            except Exception:
                value = None
        if value is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body")
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body")

    if not isinstance(value, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="JSON body must be an object")

    return value


@router.api_route("/stream", methods=["GET", "POST"])
async def stream(
    request: Request,
    current_user: User = Depends(get_current_user_flexible),
    db: AsyncSession = Depends(get_db_session),
):
    if request.method == "GET":
        question = (request.query_params.get("question") or "").strip()
        session_id_raw = request.query_params.get("session_id")
        client_msg_id = request.query_params.get("client_msg_id")
        session_id = uuid.UUID(session_id_raw) if session_id_raw else None
        payload = ChatAskRequest(question=question, session_id=session_id, client_msg_id=client_msg_id)
    else:
        body = await _read_json_body(request)
        try:
            payload = ChatAskRequest.model_validate(body)
        except ValidationError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()) from exc

    async def event_generator():
        yield _sse("meta", {"stage": "starting"})

        now = datetime.now(timezone.utc)
        settings = get_settings()

        if payload.session_id is None:
            title = payload.question.strip()
            title = title[:50] if title else None
            session = Session(user_id=current_user.id, title=title)
            db.add(session)
            await db.flush()
        else:
            session_result = await db.execute(
                select(Session).where(Session.id == payload.session_id, Session.user_id == current_user.id)
            )
            session = session_result.scalar_one_or_none()
            if session is None:
                yield _sse("error", {"message": "Session not found"})
                return

        user_message = Message(
            session_id=session.id,
            role="user",
            content=payload.question,
            client_msg_id=payload.client_msg_id,
        )
        db.add(user_message)
        await db.flush()

        yield _sse("meta", {"stage": "retrieving"})
        try:
            retrieved = await retrieve_chunks(db, query=payload.question, top_k=settings.rag_top_k)
        except (RuntimeError, httpx.HTTPError) as exc:
            yield _sse("error", {"message": f"RAG retrieval failed: {exc}"})
            return
        context = build_context(retrieved) if retrieved else None

        citations = [
            {
                "chunk_id": str(c.chunk_id),
                "document": {"title": c.title, "version": c.version, "source_url": c.source_url},
                "snippet": c.text[:240],
                "score": c.score,
            }
            for c in retrieved
        ]

        prompt = None
        if context:
            prompt = (
                "你是医疗问答助手。回答需谨慎、避免诊断与处方，必要时建议就医。\n"
                f"用户问题：{payload.question}\n\n"
                f"参考资料（带引用编号）：\n{context}\n"
            )

        qa_run = QARun(
            session_id=session.id,
            user_message_id=user_message.id,
            assistant_message_id=None,
            llm_provider=settings.llm_provider,
            llm_model=settings.llm_model or None,
            prompt_version="v1",
            prompt=prompt,
            citations=citations,
            safety_flags={"disclaimer": _DISCLAIMER, "triage": "normal"},
        )
        db.add(qa_run)
        await db.flush()

        await db.commit()

        yield _sse("meta", {"stage": "generating", "session_id": str(session.id), "qa_run_id": str(qa_run.id)})

        llm = get_llm_client()
        start = time.perf_counter()
        answer_parts: list[str] = []

        try:
            async for delta in llm.stream(question=payload.question, context=context):
                if await request.is_disconnected():
                    return
                answer_parts.append(delta)
                yield _sse("token", {"delta": delta})
        except (RuntimeError, httpx.HTTPError) as exc:
            yield _sse("error", {"message": f"LLM stream failed: {exc}"})
            return
        finally:
            latency_ms = int((time.perf_counter() - start) * 1000)

        answer = "".join(answer_parts)

        assistant_message = Message(session_id=session.id, role="assistant", content=answer)
        db.add(assistant_message)
        await db.flush()

        qa_run.assistant_message_id = assistant_message.id
        qa_run.answer = answer
        qa_run.latency_ms = latency_ms

        session.updated_at = now
        await db.commit()

        done = ChatAskResponse(
            session_id=session.id,
            qa_run_id=qa_run.id,
            answer=answer,
            citations=citations,
            safety=SafetyInfo(disclaimer=_DISCLAIMER, triage="normal"),
        )
        yield _sse("done", done.model_dump(mode="json"))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
