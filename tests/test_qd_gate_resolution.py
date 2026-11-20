"""Concrete gate defects, exclusively pure parsing and disposable clock tests."""
from contextlib import contextmanager
from math import isfinite
from types import SimpleNamespace

import pytest
from app.investment.robinhood_equity_quotes import (
    RobinhoodEquityQuoteClient,
    _float,
    _parse_ts,
)
from test_quality_dips_read_capability import setup_read


def row(symbol="SPY"):
    return {"tokenSymbol": symbol, "bid": "39.9", "ask": "40", "generatedAt": "2026-10-23T14:00:00Z"}


@pytest.mark.parametrize("records", [[row("AAPL")], [{k: v for k, v in row().items() if k != "tokenSymbol"}], [row(), row()]])
def test_rhj_must_not_relabel_foreign_anonymous_or_ambiguous_rows(records):
    assert RobinhoodEquityQuoteClient._parse_rhj("SPY", {"quotes": records}) is None


def test_classic_explicit_foreign_symbol_is_not_requested_instrument():
    assert RobinhoodEquityQuoteClient._parse_classic("SPY", {"symbol": "AAPL", "last_trade_price": "40",
                                                            "updated_at": "2026-10-23T14:00:00Z"}) is None


@pytest.mark.parametrize("value", [float("inf"), "Infinity", True, 10 ** 1000])
def test_nonfinite_boolean_or_overflow_price_is_not_a_quote(value):
    assert _float(value) is None


def test_timezone_free_provider_timestamp_is_not_locally_authenticated():
    assert _parse_ts("2026-10-23T14:00:00") is None


def test_explicit_offset_is_normalized_without_system_timezone_assumptions():
    assert _parse_ts("2026-10-23T09:00:00-05:00").isoformat() == "2026-10-23T14:00:00+00:00"


def test_matching_instrument_among_foreign_rows_remains_supported():
    quote = RobinhoodEquityQuoteClient._parse_rhj("SPY", {"quotes": [row("AAPL"), row()]})
    assert quote["symbol"] == "SPY" and quote["price"] == 40


def test_finite_bid_ask_midpoint_does_not_overflow():
    quote = RobinhoodEquityQuoteClient._parse_rhj("SPY", {"quotes": [{**row(), "bid": "1e308", "ask": "1e308"}]})
    assert isfinite(quote["midpoint"])


@pytest.mark.parametrize("mutation", ["future_observation", "future_caller_clock"])
def test_read_verifier_cannot_trust_caller_clock_over_its_own_clock(tmp_path, mutation):
    x = setup_read(tmp_path)
    payload = x.cap.read_committed(x.s.service.account, x.s.service.epoch)
    fake_now = x.s.now[0] + 10000
    if mutation == "future_observation":
        payload["observed_at"] = fake_now
    assert x.cap.verify(payload, account_id=x.s.service.account, epoch=x.s.service.epoch,
                        now=fake_now)["verified"] is False


@pytest.mark.parametrize("offset", [-1, 31])
def test_authority_check_cannot_hide_clock_reversal_or_expiry(tmp_path, offset):
    x = setup_read(tmp_path)
    original = x.authority.lease
    @contextmanager
    def slow_lease(enrollment, now):
        with original(enrollment, now) as lease:
            def check(pin, end):
                valid = lease.check(pin, end)
                x.s.now[0] += offset
                return valid
            yield SimpleNamespace(snapshot=lease.snapshot, check=check)
    x.authority.lease = slow_lease
    with pytest.raises(ValueError):
        x.cap.read_committed(x.s.service.account, x.s.service.epoch)
