"""
Embedding client wrapper.

Groq doesn't offer an embeddings endpoint, so this uses Hugging Face's
Inference Providers instead, via `client.feature_extraction()`. Returns
a normalized numpy vector, ready to be compared by cosine similarity.
"""
import numpy as np
from huggingface_hub import InferenceClient

from app.config import settings

_client: InferenceClient | None = None


def _get_client() -> InferenceClient:
    # Lazy singleton: don't construct the client (or require a token)
    # until an embedding is actually requested.
    global _client
    if _client is None:
        _client = InferenceClient(provider="hf-inference", api_key=settings.hf_token)
    return _client


def embed(text: str) -> np.ndarray:
    """Return a unit-normalized embedding vector for `text`."""
    result = _get_client().feature_extraction(text, model=settings.embedding_model)
    vector = np.array(result, dtype=np.float32)

    # Some models return a per-token matrix (tokens x dims) rather than
    # one vector per input; mean-pool across tokens if so.
    if vector.ndim == 2:
        vector = vector.mean(axis=0)

    # Normalize to unit length so that a plain dot product between two
    # vectors equals their cosine similarity.
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
    return vector