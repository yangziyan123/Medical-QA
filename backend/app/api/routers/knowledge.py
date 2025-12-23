from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
import httpx
from qdrant_client.http import models as qm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.chunk import Chunk
from app.models.document import Document
from app.rag.chunking import chunk_text
from app.rag.embeddings import embed_text, embed_texts
from app.rag.qdrant_store import ensure_collection, get_qdrant_client
from app.schemas.knowledge import (
    KnowledgeImportRequest,
    KnowledgeImportResponse,
    KnowledgeSearchItem,
    KnowledgeSearchResponse,
)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.post("/import", response_model=KnowledgeImportResponse, dependencies=[Depends(require_admin)])
async def import_knowledge(payload: KnowledgeImportRequest, db: AsyncSession = Depends(get_db_session)) -> KnowledgeImportResponse:
    settings = get_settings()
    raw = payload.raw_text.strip()
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="raw_text is empty")

    checksum = hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()
    exists = await db.execute(select(Document).where(Document.checksum == checksum))
    if exists.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Document already imported")

    doc = Document(
        source_type=payload.source_type,
        source_url=payload.source_url,
        title=payload.title.strip(),
        version=payload.version,
        checksum=checksum,
    )
    db.add(doc)
    await db.flush()

    items = chunk_text(raw)
    if not items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No chunks generated")

    chunks: list[Chunk] = []
    for item in items:
        c = Chunk(document_id=doc.id, chunk_index=item.index, text=item.text, token_count=None, section=None, meta=None)
        db.add(c)
        chunks.append(c)
    await db.flush()
    await db.commit()

    client = get_qdrant_client()
    ensure_collection(client)

    batch_size = max(1, int(settings.embedding_batch_size or 1))
    points: list[qm.PointStruct] = []
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        try:
            vectors = await embed_texts([c.text for c in batch], dim=settings.embedding_dim)
        except (RuntimeError, httpx.HTTPError) as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Embedding failed: {exc}") from exc
        for c, vec in zip(batch, vectors, strict=True):
            points.append(
                qm.PointStruct(
                    id=str(c.id),
                    vector=vec,
                    payload={
                        "chunk_id": str(c.id),
                        "document_id": str(doc.id),
                        "title": doc.title,
                        "version": doc.version,
                        "source_url": doc.source_url,
                        "chunk_index": c.chunk_index,
                    },
                )
            )

    client.upsert(collection_name=settings.qdrant_collection, points=points)

    return KnowledgeImportResponse(document_id=doc.id, chunk_count=len(chunks))


@router.get("/search", response_model=KnowledgeSearchResponse, dependencies=[Depends(require_admin)])
async def search_knowledge(
    q: str = Query(min_length=1, max_length=4000),
    top_k: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
) -> KnowledgeSearchResponse:
    settings = get_settings()
    client = get_qdrant_client()
    ensure_collection(client)

    try:
        query_vec = await embed_text(q, dim=settings.embedding_dim)
    except (RuntimeError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Embedding failed: {exc}") from exc
    try:
        if hasattr(client, "query_points"):
            resp = client.query_points(
                collection_name=settings.qdrant_collection,
                query=query_vec,
                limit=top_k,
                with_payload=True,
                with_vectors=False,
            )
            hits = list(resp.points)
        else:
            hits = client.search(  # type: ignore[attr-defined]
                collection_name=settings.qdrant_collection,
                query_vector=query_vec,
                limit=top_k,
                with_payload=True,
            )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Qdrant search failed: {exc}") from exc

    chunk_ids: list[uuid.UUID] = []
    scored: dict[uuid.UUID, float] = {}
    for h in hits:
        payload = h.payload or {}
        try:
            cid = uuid.UUID(str(payload.get("chunk_id") or h.id))
        except Exception:
            continue
        chunk_ids.append(cid)
        scored[cid] = float(h.score or 0.0)

    if not chunk_ids:
        return KnowledgeSearchResponse(items=[])

    result = await db.execute(
        select(Chunk, Document)
        .join(Document, Chunk.document_id == Document.id)
        .where(Chunk.id.in_(chunk_ids))
    )
    rows = result.all()

    items: list[KnowledgeSearchItem] = []
    for chunk, doc in rows:
        score = scored.get(chunk.id, 0.0)
        items.append(
            KnowledgeSearchItem(
                chunk_id=chunk.id,
                document_id=doc.id,
                title=doc.title,
                version=doc.version,
                source_url=doc.source_url,
                chunk_index=chunk.chunk_index,
                score=score,
                text=chunk.text,
            )
        )

    items.sort(key=lambda x: x.score, reverse=True)
    return KnowledgeSearchResponse(items=items)
