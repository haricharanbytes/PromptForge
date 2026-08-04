"""
Abstract cache interface.

Every caching strategy (naive, prefix, semantic) implements this same
interface. That lets the gateway and the benchmark harness swap
strategies without changing any other code — same pattern you'd see in
a real caching library.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CacheResult:
    hit: bool
    answer: str | None = None
    # For strategies that can report a similarity/confidence score
    # (e.g. semantic cache), otherwise None.
    score: float | None = None
    # The original question text of the nearest stored entry, if any —
    # populated whether this was a hit OR a miss, so a miss can still
    # show "here's what it almost matched, and why it didn't count."
    matched_query: str | None = None


class BaseCache(ABC):
    """Common interface for all cache strategies."""

    @abstractmethod
    def get(self, user_message: str) -> CacheResult:
        """Look up a cached answer for this message. Never calls the API."""
        raise NotImplementedError

    @abstractmethod
    def set(self, user_message: str, answer: str) -> None:
        """Store an answer for this message."""
        raise NotImplementedError

    def clear(self) -> None:
        """Optional: wipe the cache. Useful for tests/benchmarks."""
        raise NotImplementedError