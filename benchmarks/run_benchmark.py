"""
Benchmark harness.

Runs the SAME realistic query sequence (benchmarks/queries.py) through
three independent, freshly-cleared caches:

  - no_cache : baseline — every query is a real Groq call
  - naive    : NaiveCache — only exact text repeats are caught
  - semantic : SemanticCache — paraphrases are also caught, but
               near-miss traps should correctly NOT be caught

This makes real Groq + embedding API calls and takes a few minutes to
run — it's a deliberate, occasional evaluation, not something to run
on every code change (that's what the fast, free unit tests are for).

Usage:
    python -m benchmarks.run_benchmark
"""
import json
import time
from pathlib import Path

from groq import Groq

from app.cache.naive import NaiveCache
from app.cache.prefix import PrefixCache
from app.cache.semantic import SemanticCache
from app.config import settings
from app.prompts import AGRI_RESEARCH_SYSTEM_PROMPT
from benchmarks.queries import QUERY_SEQUENCE

RESULTS_DIR = Path("benchmarks/results")


def call_groq(client: Groq, prefix_cache: PrefixCache, user_message: str):
    response = client.chat.completions.create(
        model=settings.chat_model,
        messages=[
            {"role": "system", "content": AGRI_RESEARCH_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )
    stats = prefix_cache.record_usage(response.usage)
    return response.choices[0].message.content, stats


def run_strategy(name: str, cache, client: Groq) -> list[dict]:
    """cache=None means the no-cache baseline: every query is a real call."""
    prefix_cache = PrefixCache()
    results = []

    for item in QUERY_SEQUENCE:
        query = item["query"]
        start = time.time()
        score = None

        if cache is not None:
            cached = cache.get(query)
            score = cached.score
            if cached.hit:
                results.append({
                    "query": query,
                    "category": item["category"],
                    "hit": True,
                    "latency_ms": (time.time() - start) * 1000,
                    "score": score,
                    "prompt_tokens": None,
                    "cached_tokens": None,
                })
                continue

        answer, stats = call_groq(client, prefix_cache, query)
        if cache is not None:
            cache.set(query, answer)

        results.append({
            "query": query,
            "category": item["category"],
            "hit": False,
            "latency_ms": (time.time() - start) * 1000,
            "score": score,
            "prompt_tokens": stats.prompt_tokens,
            "cached_tokens": stats.cached_tokens,
        })

    return results


def check_for_trap_failures(results: list[dict]) -> list[dict]:
    """A trap query that got a HIT is a false-positive semantic match —
    the cache returned an answer for the wrong crop/value. This is the
    correctness check, separate from the performance numbers."""
    return [r for r in results if r["category"] == "near_miss_trap" and r["hit"]]


def summarize(name: str, results: list[dict]) -> dict:
    total = len(results)
    hits = sum(1 for r in results if r["hit"])
    avg_latency = sum(r["latency_ms"] for r in results) / total
    total_latency = sum(r["latency_ms"] for r in results)

    misses_with_tokens = [r for r in results if not r["hit"] and r["prompt_tokens"]]
    avg_prefix_ratio = (
        sum((r["cached_tokens"] or 0) / r["prompt_tokens"] for r in misses_with_tokens)
        / len(misses_with_tokens) * 100
        if misses_with_tokens else 0
    )

    trap_failures = check_for_trap_failures(results)

    return {
        "strategy": name,
        "total_requests": total,
        "hits": hits,
        "hit_rate_pct": round(hits / total * 100, 1),
        "avg_latency_ms": round(avg_latency, 1),
        "total_latency_ms": round(total_latency, 1),
        "avg_prefix_reuse_pct_on_miss": round(avg_prefix_ratio, 1),
        "trap_failures": [r["query"] for r in trap_failures],
    }


def main():
    client = Groq(api_key=settings.groq_api_key)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    strategies = {
        "no_cache": None,
        "naive": NaiveCache(),
        "semantic": SemanticCache(
            index_path=RESULTS_DIR / "bench_semantic.index",
            meta_path=RESULTS_DIR / "bench_semantic_meta.json",
        ),
    }

    # Every strategy starts from a clean cache, so this run is fair and
    # repeatable — no leftover state from a previous benchmark run.
    for cache in strategies.values():
        if cache is not None:
            cache.clear()

    all_results = {}
    summaries = []

    for name, cache in strategies.items():
        print(f"Running strategy: {name} ...")
        results = run_strategy(name, cache, client)
        all_results[name] = results
        summary = summarize(name, results)
        summaries.append(summary)
        print(f"  hit_rate={summary['hit_rate_pct']}%  "
              f"avg_latency={summary['avg_latency_ms']}ms  "
              f"trap_failures={len(summary['trap_failures'])}")

    (RESULTS_DIR / "raw_results.json").write_text(json.dumps(all_results, indent=2))
    (RESULTS_DIR / "summary.json").write_text(json.dumps(summaries, indent=2))

    print("\n=== SUMMARY ===")
    header = f"{'Strategy':<12}{'Hit Rate':<12}{'Avg Latency':<15}{'Total Latency':<16}{'Prefix Reuse':<14}{'Trap Failures'}"
    print(header)
    print("-" * len(header))
    for s in summaries:
        print(
            f"{s['strategy']:<12}"
            f"{s['hit_rate_pct']}%{'':<8}"
            f"{s['avg_latency_ms']}ms{'':<9}"
            f"{s['total_latency_ms']}ms{'':<8}"
            f"{s['avg_prefix_reuse_pct_on_miss']}%{'':<8}"
            f"{len(s['trap_failures'])}"
        )

    any_trap_failures = any(s["trap_failures"] for s in summaries)
    if any_trap_failures:
        print("\n⚠ WARNING: semantic cache returned a wrong-crop/value answer for a trap query:")
        for s in summaries:
            for q in s["trap_failures"]:
                print(f"  [{s['strategy']}] {q}")
        print("Consider raising SEMANTIC_CACHE_THRESHOLD in .env.")
    else:
        print("\n✓ No trap failures — semantic cache correctly distinguished all near-miss pairs.")

    print(f"\nFull results written to {RESULTS_DIR}/")


if __name__ == "__main__":
    main()