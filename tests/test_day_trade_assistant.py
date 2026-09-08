"""Day-trade DMs: LONG limits below last, R:R 1.8, no WAIT spam, no shorts."""

from app.services.day_trade_assistant import MIN_RR, _build_plan, _digest_text, _plan_embed_text


def _snap(**kw):
    base = {
        "symbol": "MSFT",
        "name": "Microsoft",
        "price": 499.68,
        "prior_close": 510.12,
        "gap_pct": -2.05,
    }
    base.update(kw)
    return base


def test_msft_prepare_has_real_limits_and_rr():
    p = _build_plan(_snap(), "OPEN")
    assert p.action == "PREPARE"
    assert p.bias == "LONG"
    assert p.l1 < 499.68 * 0.995
    assert p.l2 < p.l1
    assert p.stop < p.l2
    assert p.rr >= MIN_RR
    assert p.tp1 > p.l1
    text = _plan_embed_text(p)
    assert "L1 starter" in text
    assert "L2 add" in text
    assert "$497.28" not in text


def test_trigger_when_already_down_hard():
    p = _build_plan(_snap(symbol="TSLA", price=354.08, prior_close=376.37, gap_pct=-5.92), "OPEN")
    assert p.action == "TRIGGER"
    assert p.l1 < p.price
    assert p.rr >= MIN_RR


def test_no_short_on_gap_up():
    p = _build_plan(_snap(symbol="MU", price=1016.59, prior_close=958.16, gap_pct=6.1), "OPEN")
    assert p.action == "SKIP"
    assert p.bias == "LONG"


def test_digest_lists_limits():
    p = _build_plan(_snap(), "PREMARKET")
    text = _digest_text([p])
    assert "MSFT" in text
    assert "L1" in text
    assert "PREPARE" in text
