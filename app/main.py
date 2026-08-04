"""
FastAPI gateway entrypoint.

/chat first checks the semantic cache (which also catches exact
repeats — an exact match embeds to ~1.0 similarity with itself, so it
naturally subsumes what NaiveCache alone would catch). On a miss, it
calls Groq for a real completion, records Groq's server-side prefix-
cache savings via PrefixCache, and stores the new answer in the
semantic cache for next time.

The semantic cache is cleared once at startup, so every fresh run of
the app begins from a clean, uncontaminated state, while still
persisting correctly within a single running session (e.g. across
--reload restarts triggered by code edits).

The static dashboard (app/static/index.html) is mounted at "/" — but
that mount MUST be registered last, after every real route, or it
will swallow every request (including POST /chat) before those routes
ever get a chance to match.
"""
import time

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from groq import Groq

from app.cache.prefix import PrefixCache
from app.cache.semantic import SemanticCache
from app.config import settings
from app.models import CacheStrategy, ChatRequest, ChatResponse
from app.prompts import AGRI_RESEARCH_SYSTEM_PROMPT

app = FastAPI(
    title="PromptForge",
    description="A caching gateway for LLM chat completions, backed by Groq.",
    version="0.1.0",
)

semantic_cache = SemanticCache()
semantic_cache.clear()  # session-scoped: wipe any leftover data from a previous run
prefix_cache = PrefixCache()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/meta")
def meta() -> dict:
    """Config values the frontend needs but shouldn't hardcode."""
    return {
        "chat_model": settings.chat_model,
        "embedding_model": settings.embedding_model,
        "semantic_cache_threshold": settings.semantic_cache_threshold,
    }


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    start = time.time()
    system_prompt = req.system_prompt or AGRI_RESEARCH_SYSTEM_PROMPT

    cached = semantic_cache.get(req.user_message)
    if cached.hit:
        return ChatResponse(
            answer=cached.answer,
            cache_hit=True,
            strategy=CacheStrategy.SEMANTIC,
            latency_ms=(time.time() - start) * 1000,
            similarity_score=cached.score,
            matched_query=cached.matched_query,
        )

    if not settings.groq_api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Copy .env.example to .env and add your key."
        )

    client = Groq(api_key=settings.groq_api_key)
    response = client.chat.completions.create(
        model=settings.chat_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": req.user_message},
        ],
    )
    answer = response.choices[0].message.content
    semantic_cache.set(req.user_message, answer)
    stats = prefix_cache.record_usage(response.usage)

    return ChatResponse(
        answer=answer,
        cache_hit=False,
        strategy=CacheStrategy.NONE,
        latency_ms=(time.time() - start) * 1000,
        prompt_tokens=stats.prompt_tokens,
        cached_tokens=stats.cached_tokens,
        similarity_score=cached.score,
        matched_query=cached.matched_query,
    )


# IMPORTANT: this must be the LAST route registered. A mount at "/"
# matches every path, so anything registered after this line would be
# unreachable — FastAPI/Starlette matches routes in registration
# order, not by specificity.
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")