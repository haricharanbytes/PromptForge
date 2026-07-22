"""
Centralized configuration, loaded from environment variables / .env.

Using pydantic-settings (rather than scattered os.environ.get() calls)
means every setting is typed, validated at startup, and documented in
one place.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    #Endpoints that call Groq should check this is set.
    groq_api_key: str = ""

    # Hugging Face Inference Providers token, used for embeddings only
    # (Groq doesn't offer an embeddings endpoint).
    hf_token: str = ""

    # to report real cached_tokens (e.g. openai/gpt-oss-20b, openai/gpt-oss-120b, moonshotai/kimi-k2-instruct).
    chat_model: str = "openai/gpt-oss-20b"
    embedding_model: str = "ibm-granite/granite-embedding-97m-multilingual-r2"

    semantic_cache_threshold: float = 0.92
    cache_ttl_seconds: int = 3600


#`from app.config import settings`
settings = Settings()