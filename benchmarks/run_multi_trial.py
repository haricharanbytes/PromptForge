"""
Multi-trial benchmark runner.

A single benchmark run's latency numbers are noisy — Groq's real
response time varies run to run based on their server load, which has
nothing to do with which caching strategy is being tested (we saw
this directly: no_cache's avg latency was 4570ms in one run and
2514ms in another). Running the full benchmark N times and reporting
the mean and standard deviation of each metric is what actually makes
a latency comparison across strategies trustworthy, rather than a
fluke of one lucky or unlucky run.

Reuses run_strategy() and summarize() from run_benchmark.py directly —
"one trial" should mean exactly the same thing here as it does there;
duplicating that logic would risk the two scripts silently drifting
apart over time.

Usage:
    python -m benchmarks.run_multi_trial --trials 3
"""
import argparse
import json
import statistics
from pathlib import Path

from groq import Groq

from app.cache.naive import NaiveCache
from app.cache.semantic import SemanticCache
from app.config import settings
from benchmarks.run_benchmark import run_strategy, summarize

RESULTS_DIR = Path("benchmarks/results")


def run_trials(n_trials: int) -> dict[str, list[dict]]:
    client = Groq(api_key=settings.groq_api_key)
    all_summaries: dict[str, list[dict]] = {"no_cache": [], "naive": [], "semantic": []}

    for trial in range(1, n_trials + 1):
        print(f"\n=== Trial {trial}/{n_trials} ===")

        # Each trial's semantic cache gets its own files, so trials
        # never contaminate each other's cache state — same isolation
        # principle as the tmp_path fixture in the unit tests.
        strategies = {
            "no_cache": None,
            "naive": NaiveCache(),
            "semantic": SemanticCache(
                index_path=RESULTS_DIR / f"trial_{trial}_semantic.index",
                meta_path=RESULTS_DIR / f"trial_{trial}_semantic_meta.json",
            ),
        }
        for cache in strategies.values():
            if cache is not None:
                cache.clear()

        for name, cache in strategies.items():
            results = run_strategy(name, cache, client)
            summary = summarize(name, results)
            all_summaries[name].append(summary)
            print(
                f"  [{name}] hit_rate={summary['hit_rate_pct']}%  "
                f"avg_latency={summary['avg_latency_ms']}ms  "
                f"trap_failures={len(summary['trap_failures'])}"
            )

    return all_summaries


def aggregate(all_summaries: dict[str, list[dict]]) -> list[dict]:
    aggregated = []
    for name, trials in all_summaries.items():
        hit_rates = [t["hit_rate_pct"] for t in trials]
        avg_latencies = [t["avg_latency_ms"] for t in trials]
        prefix_reuse = [t["avg_prefix_reuse_pct_on_miss"] for t in trials]
        total_trap_failures = sum(len(t["trap_failures"]) for t in trials)

        aggregated.append({
            "strategy": name,
            "n_trials": len(trials),
            "hit_rate_pct_mean": round(statistics.mean(hit_rates), 1),
            "hit_rate_pct_stdev": round(statistics.stdev(hit_rates), 1) if len(hit_rates) > 1 else 0.0,
            "avg_latency_ms_mean": round(statistics.mean(avg_latencies), 1),
            "avg_latency_ms_stdev": round(statistics.stdev(avg_latencies), 1) if len(avg_latencies) > 1 else 0.0,
            "avg_prefix_reuse_pct_mean": round(statistics.mean(prefix_reuse), 1),
            "total_trap_failures_across_all_trials": total_trap_failures,
        })
    return aggregated


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=3)
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    all_summaries = run_trials(args.trials)
    aggregated = aggregate(all_summaries)

    (RESULTS_DIR / "multi_trial_summary.json").write_text(json.dumps(aggregated, indent=2))

    print(f"\n=== AGGREGATED OVER {args.trials} TRIALS ===")
    header = f"{'Strategy':<12}{'Hit Rate':<20}{'Avg Latency':<22}{'Prefix Reuse':<16}{'Trap Failures (total)'}"
    print(header)
    print("-" * len(header))
    for s in aggregated:
        print(
            f"{s['strategy']:<12}"
            f"{s['hit_rate_pct_mean']}% ± {s['hit_rate_pct_stdev']}{'':<8}"
            f"{s['avg_latency_ms_mean']}ms ± {s['avg_latency_ms_stdev']}{'':<6}"
            f"{s['avg_prefix_reuse_pct_mean']}%{'':<10}"
            f"{s['total_trap_failures_across_all_trials']}"
        )

    print(f"\nFull results written to {RESULTS_DIR}/multi_trial_summary.json")


if __name__ == "__main__":
    main()