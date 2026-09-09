"""1h trend filter: paper pullbacks with the hour, never fade it."""

from app.services.perp_micro_coach import _trend_from_closes, htf_allows_side


def test_uptrend_allows_long_blocks_short():
    closes = [100 + i * 0.4 for i in range(30)]
    assert _trend_from_closes(closes) == "UP"
    assert htf_allows_side("LONG", "UP") is True
    assert htf_allows_side("SHORT", "UP") is False


def test_downtrend_allows_short_blocks_long():
    closes = [100 - i * 0.4 for i in range(30)]
    assert _trend_from_closes(closes) == "DOWN"
    assert htf_allows_side("SHORT", "DOWN") is True
    assert htf_allows_side("LONG", "DOWN") is False


def test_chop_is_flat_and_blocks_both():
    closes = [100, 100.1, 99.9, 100.05, 99.95] * 6
    assert _trend_from_closes(closes) == "FLAT"
    assert htf_allows_side("LONG", "FLAT") is False
    assert htf_allows_side("SHORT", "FLAT") is False


def test_missing_htf_data_does_not_freeze_paper():
    assert _trend_from_closes([]) == "UNKNOWN"
    assert _trend_from_closes([100.0] * 10) == "UNKNOWN"
    assert htf_allows_side("LONG", "UNKNOWN") is True
    assert htf_allows_side("SHORT", "UNKNOWN") is True
