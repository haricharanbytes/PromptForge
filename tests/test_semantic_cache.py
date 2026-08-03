"""
Tests for SemanticCache.

We monkeypatch `embed()` so these tests never call the real Hugging
Face API — no network, no API key needed, no flakiness, runs in
milliseconds. We're testing the CACHE's logic (storage, retrieval,
threshold behavior, numeric guard), not the embedding model's quality.
"""
import numpy as np
import pytest

from app.cache.semantic import SemanticCache


def fake_embed(text: str) -> np.ndarray:
    """Deterministic fake: same text -> same vector, different text ->
    a different, unit-normalized vector. Good enough to test cache
    mechanics without needing real semantic meaning."""
    seed = abs(hash(text)) % (2**32)
    rng = np.random.default_rng(seed)
    vector = rng.standard_normal(384).astype(np.float32)
    return vector / np.linalg.norm(vector)


@pytest.fixture(autouse=True)
def patch_embed(monkeypatch):
    monkeypatch.setattr("app.cache.semantic.embed", fake_embed)


@pytest.fixture
def cache(tmp_path):
    return SemanticCache(
        index_path=tmp_path / "test.index",
        meta_path=tmp_path / "test_meta.json",
    )


def test_miss_on_empty_cache(cache):
    result = cache.get("What is the seed rate for HD-3086 wheat?")
    assert result.hit is False
    assert result.score is None


def test_exact_text_is_a_hit(cache):
    cache.set("What is the seed rate for HD-3086 wheat?", "100 kg/ha.")
    result = cache.get("What is the seed rate for HD-3086 wheat?")
    assert result.hit is True
    assert result.answer == "100 kg/ha."
    assert result.score == pytest.approx(1.0, abs=1e-4)


def test_persists_across_instances(tmp_path):
    index_path = tmp_path / "test.index"
    meta_path = tmp_path / "test_meta.json"

    cache1 = SemanticCache(index_path=index_path, meta_path=meta_path)
    cache1.set("What is the seed rate for HD-3086 wheat?", "100 kg/ha.")

    cache2 = SemanticCache(index_path=index_path, meta_path=meta_path)
    result = cache2.get("What is the seed rate for HD-3086 wheat?")
    assert result.hit is True
    assert result.answer == "100 kg/ha."


def test_numeric_guard_blocks_different_value(cache, monkeypatch):
    """Regression test for a real bug found via benchmarking: two
    questions differing only in a number (e.g. pH 5.2 vs pH 8.0) can
    embed as near-identical despite having different correct answers.
    The numeric guard must block this even when similarity is high."""
    same_vector = fake_embed("pH question template")
    monkeypatch.setattr("app.cache.semantic.embed", lambda text: same_vector)

    cache.set("Is a soil pH of 5.2 too acidic for wheat?", "Yes, 5.2 is below the 6.0-7.5 range.")
    result = cache.get("Is a soil pH of 8.0 too acidic for wheat?")

    assert result.hit is False, "Numeric guard should have blocked this despite high similarity"


def test_numeric_guard_allows_matching_value(cache, monkeypatch):
    """Sanity check: the guard should NOT block a true paraphrase that
    happens to share the same number (e.g. HD-3086 in both)."""
    same_vector = fake_embed("seed rate template")
    monkeypatch.setattr("app.cache.semantic.embed", lambda text: same_vector)

    cache.set("What is the seed rate for HD-3086 wheat?", "100 kg/ha.")
    result = cache.get("How much seed do I need per hectare for HD-3086?")

    assert result.hit is True
    assert result.answer == "100 kg/ha."