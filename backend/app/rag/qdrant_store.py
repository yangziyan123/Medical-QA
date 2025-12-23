from __future__ import annotations

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.core.config import get_settings


def get_qdrant_client() -> QdrantClient:
    settings = get_settings()
    return QdrantClient(url=settings.qdrant_url)


def ensure_collection(client: QdrantClient) -> None:
    settings = get_settings()
    name = settings.qdrant_collection

    if client.collection_exists(name):
        info = client.get_collection(name)
        vectors = info.config.params.vectors
        size = None
        if isinstance(vectors, qm.VectorParams):
            size = vectors.size
        elif isinstance(vectors, dict) and vectors:
            size = next(iter(vectors.values())).size

        if size is not None and size != settings.embedding_dim:
            raise RuntimeError(
                f"Qdrant collection '{name}' vector size is {size}, but EMBEDDING_DIM is {settings.embedding_dim}. "
                "Drop the collection or align EMBEDDING_DIM."
            )
        return

    client.create_collection(
        collection_name=name,
        vectors_config=qm.VectorParams(size=settings.embedding_dim, distance=qm.Distance.COSINE),
    )
