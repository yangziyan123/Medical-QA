from __future__ import annotations

import hashlib
import math
from typing import List

import httpx

from app.core.config import get_settings


def embed_text_stub(text: str, *, dim: int) -> List[float]:
    """
    Deterministic embedding for development:
    - No external model dependency
    - Stable across runs
    - Produces unit-length vector
    """
    if dim <= 0:
        raise ValueError("dim must be positive")

    vec = [0.0] * dim
    data = text.encode("utf-8", errors="ignore")
    digest = hashlib.sha256(data).digest()

    for i in range(dim):
        b = digest[i % len(digest)]
        v = (b / 255.0) * 2.0 - 1.0
        vec[i] = v

    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


async def embed_text(text: str, *, dim: int) -> list[float]:
    return (await embed_texts([text], dim=dim))[0]


async def embed_texts(texts: list[str], *, dim: int) -> list[list[float]]:
    settings = get_settings()
    provider = (settings.embedding_provider or "stub").lower()

    if provider in {"stub", "dev"}:
        return [embed_text_stub(t, dim=dim) for t in texts]

    if provider not in {"openai_compat", "openai-compatible", "volcengine", "ark"}:
        raise RuntimeError(f"Unsupported embedding provider: {settings.embedding_provider}")

    if not settings.embedding_model:
        raise RuntimeError("Embedding model is empty; set EMBEDDING_MODEL")

    base_url = settings.embedding_base_url.rstrip("/")
    headers = {"Content-Type": "application/json"}
    if settings.embedding_api_key:
        headers["Authorization"] = f"Bearer {settings.embedding_api_key}"

    payload = {"model": settings.embedding_model, "input": texts}

    async with httpx.AsyncClient(base_url=base_url, timeout=settings.embedding_timeout_sec) as client:
        resp = await client.post("/embeddings", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    items = data.get("data") if isinstance(data, dict) else None
    if not isinstance(items, list) or not items:
        raise RuntimeError("Embedding response missing data[]")

    # Ensure embeddings are returned in the input order.
    def _idx(x: dict) -> int:
        v = x.get("index")
        return int(v) if isinstance(v, int) else 0

    items = sorted([x for x in items if isinstance(x, dict)], key=_idx)

    vectors: list[list[float]] = []
    for item in items:
        raw = item.get("embedding") or item.get("vector")
        if not isinstance(raw, list):
            continue
        vec = [float(x) for x in raw]
        if len(vec) != dim:
            raise RuntimeError(f"Embedding dim mismatch: got {len(vec)}, expected {dim}")
        if settings.embedding_normalize:
            vec = _normalize(vec)
        vectors.append(vec)

    if len(vectors) != len(texts):
        raise RuntimeError(f"Embedding count mismatch: got {len(vectors)}, expected {len(texts)}")

    return vectors
