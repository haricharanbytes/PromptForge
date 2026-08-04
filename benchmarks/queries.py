"""
Benchmark query sequence.

Designed to look like a realistic session against the agri-research
assistant — not random questions, but a deliberate mix that stresses
each caching strategy differently:

- "novel"        — first time this exact meaning has come up
- "exact_repeat"  — identical text to an earlier query (naive cache's
                    one strength)
- "paraphrase"    — same meaning, different wording (naive cache
                    should MISS this; semantic cache should HIT)
- "near_miss_trap"— lexically very similar to an earlier query, but
                    asks about a DIFFERENT crop/value and therefore
                    has a DIFFERENT correct answer. This is the
                    critical test: if the semantic cache wrongly hits
                    on one of these, it's returning a factually wrong
                    answer with false confidence. This is what the
                    similarity-score threshold exists to prevent.
- "unrelated"     — nothing to do with anything else in the sequence
"""

QUERY_SEQUENCE = [
    {"query": "What is the seed rate for HD-3086 wheat?", "category": "novel"},
    {"query": "How much fertilizer nitrogen does maize DHM-117 need?", "category": "novel"},
    {"query": "What is the seed rate for HD-3086 wheat?", "category": "exact_repeat"},
    {"query": "How much seed do I need per hectare for HD-3086?", "category": "paraphrase"},
    {"query": "What is the seed rate for Pusa Basmati 1121 rice?", "category": "near_miss_trap"},

    {"query": "What pH requires lime correction?", "category": "novel"},
    {"query": "Is a soil pH of 5.2 too acidic for wheat?", "category": "novel"},
    {"query": "Is a soil pH of 8.0 too acidic for wheat?", "category": "near_miss_trap"},

    {"query": "How long should raw field data be archived?", "category": "novel"},
    {"query": "What is the retention period for raw field data?", "category": "paraphrase"},

    {"query": "What is the recommended row spacing for maize DHM-117?", "category": "novel"},
    {"query": "What is the recommended row spacing for HD-3086 wheat?", "category": "near_miss_trap"},

    {"query": "Can you recommend a fungicide for yellow rust?", "category": "novel"},
    {"query": "What fungicide should I use for yellow rust in wheat?", "category": "paraphrase"},

    {"query": "What is the capital of France?", "category": "unrelated"},
    {"query": "What is the seed rate for HD-3086 wheat?", "category": "exact_repeat"},
]