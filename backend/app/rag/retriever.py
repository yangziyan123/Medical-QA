from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.rag.embeddings import embed_text
from app.rag.qdrant_store import ensure_collection, get_qdrant_client


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    title: str
    version: str | None
    source_url: str | None
    chunk_index: int
    score: float
    text: str


async def retrieve_chunks(db: AsyncSession, *, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
    settings = get_settings()
    k = top_k or settings.rag_top_k

    client = get_qdrant_client()
    ensure_collection(client)

    vec = await embed_text(query, dim=settings.embedding_dim)

    if hasattr(client, "query_points"):
        resp = client.query_points(
            collection_name=settings.qdrant_collection,
            query=vec,
            limit=k,
            with_payload=True,
            with_vectors=False,
        )
        points = list(resp.points)
    else:
        points = client.search(  # type: ignore[attr-defined]
            collection_name=settings.qdrant_collection,
            query_vector=vec,
            limit=k,
            with_payload=True,
        )

    scored: list[tuple[uuid.UUID, float]] = []
    for p in points:
        payload = p.payload or {}
        try:
            cid = uuid.UUID(str(payload.get("chunk_id") or p.id))
        except Exception:
            continue
        scored.append((cid, float(p.score or 0.0)))

    if not scored:
        return []

    chunk_ids = [cid for cid, _ in scored]
    score_map = {cid: s for cid, s in scored}

    result = await db.execute(
        select(Chunk, Document)
        .join(Document, Chunk.document_id == Document.id)
        .where(Chunk.id.in_(chunk_ids))
    )
    rows = result.all()

    by_id: dict[uuid.UUID, RetrievedChunk] = {}
    for chunk, doc in rows:
        by_id[chunk.id] = RetrievedChunk(
            chunk_id=chunk.id,
            document_id=doc.id,
            title=doc.title,
            version=doc.version,
            source_url=doc.source_url,
            chunk_index=chunk.chunk_index,
            score=score_map.get(chunk.id, 0.0),
            text=chunk.text,
        )

    ordered: list[RetrievedChunk] = []
    for cid, _ in scored:
        item = by_id.get(cid)
        if item:
            ordered.append(item)
    return ordered


def build_context(chunks: list[RetrievedChunk], *, max_chars: int = 6000) -> str:
    parts: list[str] = []
    used = 0
    for i, c in enumerate(chunks, start=1):
        header = f"[CIT-{i}] {c.title} {('(' + c.version + ')') if c.version else ''}\n"
        body = c.text.strip()
        block = f"{header}{body}\n"
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    return "\n".join(parts).strip()
