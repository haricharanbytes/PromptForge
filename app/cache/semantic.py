"""
Semantic (embedding-based) cache, backed by FAISS.

Stores every (question, answer) pair as a normalized embedding vector,
PLUS the original question text alongside the answer — needed for the
numeric guard below.

On lookup, embeds the incoming question and searches for its nearest
neighbor by cosine similarity (implemented as inner product on unit
vectors — see app/embeddings.py). If the best match clears
settings.semantic_cache_threshold, it's a CANDIDATE hit — but before
returning it, a numeric guard checks whether both questions reference
the same numbers. Embedding similarity is weak at distinguishing a
single differing number in an otherwise near-identical sentence (e.g.
"pH of 5.2" vs "pH of 8.0" embed as almost the same question, but have
opposite correct answers) — this guard catches that specific failure
mode without needing a stricter (and less useful) global threshold.

Persisted to disk (data/semantic.index + data/semantic_meta.json) so
the cache survives app restarts.
"""
import json
import re
from pathlib import Path

import faiss
import numpy as np

from app.cache.base import BaseCache, CacheResult
from app.config import settings
from app.embeddings import embed

EMBEDDING_DIM = 384  # must match the embedding model's output size

INDEX_PATH = Path("data/semantic.index")
META_PATH = Path("data/semantic_meta.json")

NUMBER_PATTERN = re.compile(r"\d+\.?\d*")


def _extract_numbers(text: str) -> set[str]:
    """All numeric substrings in text, as a set (order doesn't matter).
    Kept as strings, not floats — "3086" and "3086.0" should count as
    different if they ever appeared that way; we want exact textual
    match, not numeric equality."""
    return set(NUMBER_PATTERN.findall(text))


class SemanticCache(BaseCache):
    def __init__(self, index_path: Path = INDEX_PATH, meta_path: Path = META_PATH) -> None:
        self._index_path = index_path
        self._meta_path = meta_path

        self._index = faiss.IndexFlatIP(EMBEDDING_DIM)

        # Each entry stores both the original question and its answer.
        # FAISS only knows about vectors + integer positions; this list
        # is how we translate a FAISS match back into something we can
        # both return (the answer) and safety-check (the question).
        self._entries: list[dict] = []

        self._last_embedded_text: str | None = None
        self._last_vector: np.ndarray | None = None

        self._load()

    def _embed_cached(self, user_message: str) -> np.ndarray:
        if user_message == self._last_embedded_text:
            return self._last_vector
        vector = embed(user_message)
        self._last_embedded_text = user_message
        self._last_vector = vector
        return vector

    def get(self, user_message: str) -> CacheResult:
        if self._index.ntotal == 0:
            return CacheResult(hit=False)

        query_vector = self._embed_cached(user_message).reshape(1, -1)
        scores, indices = self._index.search(query_vector, k=1)
        best_score = float(scores[0][0])
        best_idx = int(indices[0][0])
        candidate = self._entries[best_idx]

        if best_score < settings.semantic_cache_threshold:
            return CacheResult(hit=False, score=best_score, matched_query=candidate["query"])

        # Candidate hit by similarity — now apply the numeric guard.
        incoming_numbers = _extract_numbers(user_message)
        candidate_numbers = _extract_numbers(candidate["query"])

        if incoming_numbers != candidate_numbers:
            # High semantic similarity, but the specific numbers differ
            # (or one has numbers the other doesn't) — treat as a miss
            # rather than risk returning an answer for the wrong value.
            # matched_query is still reported, so it's visible *what*
            # was almost matched and blocked.
            return CacheResult(hit=False, score=best_score, matched_query=candidate["query"])

        return CacheResult(
            hit=True,
            answer=candidate["answer"],
            score=best_score,
            matched_query=candidate["query"],
        )

    def set(self, user_message: str, answer: str) -> None:
        vector = self._embed_cached(user_message).reshape(1, -1)
        self._index.add(vector)
        self._entries.append({"query": user_message, "answer": answer})
        self._save()

    def clear(self) -> None:
        self._index = faiss.IndexFlatIP(EMBEDDING_DIM)
        self._entries = []
        self._last_embedded_text = None
        self._last_vector = None
        self._save()

    def _save(self) -> None:
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(self._index_path))
        self._meta_path.write_text(json.dumps(self._entries))

    def _load(self) -> None:
        if self._index_path.exists() and self._meta_path.exists():
            self._index = faiss.read_index(str(self._index_path))
            self._entries = json.loads(self._meta_path.read_text())