from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkItem:
    index: int
    text: str


def chunk_text(raw_text: str, *, max_chars: int = 1200, overlap_chars: int = 120) -> list[ChunkItem]:
    text = raw_text.strip()
    if not text:
        return []

    parts = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    merged: list[str] = []
    buf = ""
    for p in parts:
        if not buf:
            buf = p
            continue
        if len(buf) + 2 + len(p) <= max_chars:
            buf = f"{buf}\n\n{p}"
        else:
            merged.append(buf)
            buf = p
    if buf:
        merged.append(buf)

    chunks: list[ChunkItem] = []
    for i, m in enumerate(merged):
        if len(m) <= max_chars:
            chunks.append(ChunkItem(index=i, text=m))
            continue

        start = 0
        piece_index = i
        while start < len(m):
            end = min(len(m), start + max_chars)
            piece = m[start:end]
            chunks.append(ChunkItem(index=piece_index, text=piece))
            piece_index += 1
            if end >= len(m):
                break
            start = max(0, end - overlap_chars)

    return chunks

