"""Day-trade alerts use quality-dip ladders, not 0.3% scalp zones."""

from app.services.day_trade_assistant import _build_plan, _digest_text, _plan_embed_text


def _snap(**kw):
    base = {
        "symbol": "MSFT",
        "name": "Microsoft",
        "price": 499.68,
        "prior_close": 510.12,
        "gap_pct": -2.05,
        "ret_1d": -0.0205,
        "ret_5d": -0.03,
        "drawdown": 0.10,
        "high_52w": 555.0,
    }
    base.update(kw)
    return base


def test_msft_limits_are_percent_not_a_dollar():
    p = _build_plan(_snap(), "OPEN")
    assert p.bias == "LONG"
    assert p.ladder
    t1 = p.ladder[0]["limit"]
    # Old bot: $497–$498. New: 3% below last ≈ $484.69
    assert t1 < 490
    assert abs(t1 - 499.68 * 0.97) < 0.5
    assert p.ladder[-1]["pct_below"] == 18.0
    assert p.stance in ("WAIT_CHEAPER", "WATCH", "SCALE_SMALL")


def test_adbe_dump_is_not_a_buy_the_ask():
    p = _build_plan(
        _snap(
            symbol="ADBE",
            name="Adobe",
            price=266.51,
            prior_close=285.75,
            gap_pct=-6.73,
            ret_1d=-0.0673,
            ret_5d=-0.078,
            drawdown=0.614,
        ),
        "OPEN",
    )
    assert p.stance != "SCALE_SMALL"
    assert p.trap or p.stance == "WAIT_CHEAPER"
    assert p.ladder[0]["limit"] < 266.51
    text = _plan_embed_text(p)
    assert "3%" in text or "below last" in text.lower() or "WAIT" in text


def test_never_short_quality_names():
    p = _build_plan(
        _snap(symbol="MU", price=1016.59, prior_close=958.16, gap_pct=6.1, ret_1d=0.061, drawdown=0.05),
        "OPEN",
    )
    assert p.bias == "LONG"


def test_wait_digest_lists_t1():
    p = _build_plan(_snap(), "OPEN")
    text = _digest_text([p])
    assert "MSFT" in text
    assert "T1" in text
    assert "0.3%" not in text
