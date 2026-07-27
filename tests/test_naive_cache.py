from app.cache.naive import NaiveCache


def test_miss_then_hit():
    cache = NaiveCache()

    result = cache.get("What is the seed rate for HD-3086 wheat?")
    assert result.hit is False

    cache.set("What is the seed rate for HD-3086 wheat?", "100 kg/ha, row spacing 20-22 cm.")
    result = cache.get("What is the seed rate for HD-3086 wheat?")
    assert result.hit is True
    assert result.answer == "100 kg/ha, row spacing 20-22 cm."


def test_different_phrasing_misses():
    cache = NaiveCache()
    cache.set("What is the seed rate for HD-3086 wheat?", "100 kg/ha, row spacing 20-22 cm.")

    result = cache.get("How much seed for HD-3086?")
    assert result.hit is False