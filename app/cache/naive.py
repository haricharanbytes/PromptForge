"""
Naive exact-match cache.

Hashes the user message and does a dictionary lookup. Only ever hits
on an exact repeat of a message seen before. This is the baseline the
semantic cache gets benchmarked against later.
"""
import hashlib

from app.cache.base import BaseCache, CacheResult


class NaiveCache(BaseCache):
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def _key(self, user_message: str) -> str:
        return hashlib.sha256(user_message.encode()).hexdigest()

    def get(self, user_message: str) -> CacheResult:
        key = self._key(user_message)
        if key in self._store:
            return CacheResult(hit=True, answer=self._store[key])
        return CacheResult(hit=False)

    def set(self, user_message: str, answer: str) -> None:
        self._store[self._key(user_message)] = answer

    def clear(self) -> None:
        self._store.clear()