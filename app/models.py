"""Request/response schemas for the gateway API."""
from enum import Enum

from pydantic import BaseModel, Field


class CacheStrategy(str, Enum):
    """Which caching strategy served (or will serve) a request."""

    NAIVE = "naive"
    PREFIX = "prefix"
    SEMANTIC = "semantic"
    NONE = "none"  # cache miss, went straight to the model


class ChatRequest(BaseModel):
    user_message: str = Field(..., min_length=1)
    system_prompt: str | None = None


class ChatResponse(BaseModel):
    answer: str
    cache_hit: bool
    strategy: CacheStrategy
    latency_ms: float
    prompt_tokens: int | None = None
    cached_tokens: int | None = None
    similarity_score: float | None = None  # how close the best match was, hit or miss