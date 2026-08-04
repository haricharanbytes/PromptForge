from groq import Groq

from app.cache.prefix import PrefixCache
from app.config import settings
from app.prompts import AGRI_RESEARCH_SYSTEM_PROMPT

client = Groq(api_key=settings.groq_api_key)
prefix_cache = PrefixCache()

questions = [
    "What's the seed rate for HD-3086 wheat?",
    "How much fertilizer nitrogen does maize DHM-117 need?",
]

for q in questions:
    response = client.chat.completions.create(
        model=settings.chat_model,
        messages=[
            {"role": "system", "content": AGRI_RESEARCH_SYSTEM_PROMPT},
            {"role": "user", "content": q},
        ],
    )
    stats = prefix_cache.record_usage(response.usage)
    print(q)
    print(f"  prompt_tokens={stats.prompt_tokens} cached_tokens={stats.cached_tokens} ratio={stats.cache_ratio:.2%}")