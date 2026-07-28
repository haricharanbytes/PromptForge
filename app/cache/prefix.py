"""
Prefix/KV-aware cache.

Prefix caching isn't something this class implements itself — Groq's
servers already do it: when consecutive requests share a long,
identical prefix (like our static AGRI_RESEARCH_SYSTEM_PROMPT), the
model reuses the internal attention state for that shared prefix
instead of recomputing it from scratch. Our job here is just to detect
and report how much of that saving is happening, using the `usage`
object Groq returns with every response.

This inherits NaiveCache's exact-match get/set (an exact repeat is
still an instant, zero-cost hit) and adds tracking for the server-side
prefix savings that apply even on a MISS.
"""
from dataclasses import dataclass

from app.cache.naive import NaiveCache


@dataclass
class PrefixCacheStats:
    prompt_tokens: int
    cached_tokens: int

    @property
    def cache_ratio(self) -> float:
        """Fraction of the prompt served from Groq's server-side prefix cache."""
        if self.prompt_tokens == 0:
            return 0.0
        return self.cached_tokens / self.prompt_tokens


class PrefixCache(NaiveCache):
    """Exact-match cache that also tracks server-side prefix cache savings."""

    def __init__(self) -> None:
        super().__init__()
        self.last_stats: PrefixCacheStats | None = None

    def record_usage(self, usage) -> PrefixCacheStats:
        """Call this with the `usage` object from a Groq chat completion
        response — even on a cache MISS, since the prefix saving happens
        server-side regardless of whether our own exact-match cache hit."""
        cached_tokens = getattr(
            getattr(usage, "prompt_tokens_details", None), "cached_tokens", None
        ) or 0
        stats = PrefixCacheStats(
            prompt_tokens=usage.prompt_tokens,
            cached_tokens=cached_tokens,
        )
        self.last_stats = stats
        return stats