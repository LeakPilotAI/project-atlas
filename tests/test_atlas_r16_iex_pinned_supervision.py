"""Offline-only coverage of R16 bounded pinned IEX observation supervision.

Exact writer instances below are intentionally uninitialized Python test doubles.
No native financial enrollment, provider credentials, sockets or account files.
"""
from __future__ import annotations

import copy
import time

import pytest
from app.investment.alpaca_iex import Credentials, IEXFeed
from app.services.quality_dips_unified_writer import EnrolledQualityDipsWriter

from scripts.observation_runtime import atlas_r16_iex_pinned_supervision as supervised
from scripts.observation_runtime.atlas_r16_joint_ntp_iex_data_only import (
    NativeUtcUpperBound,
    ntp_module,
)
from scripts.observation_runtime.atlas_r16_owned_iex_shortlist import (
    NativeQDPositionPins,
)


class TestOnlyClock:
    """Never a genuine native clock issuer; synthetic contract-validation only."""

    def runtime_sample(self):
        return {
            "schema": "QD_AUTO_CLOCK_V3", "source_id": ntp_module.SOURCE,
            "utc": 1794420000, "uncertainty_ms": 140,
            "monotonic_ns": time.perf_counter_ns(),
        }

    def verify_runtime_sample(self, sample):
        return True


def fixture(held=None):
    writer = object.__new__(EnrolledQualityDipsWriter)
    writer.runtime = object()
    writer.authority = object()
    writer.store = object()
    writer.manifest = {"epoch": "SYNTHETIC_NO_NATIVE_FINANCIAL_ACCOUNT"}
    cut = {
        "manifest": copy.deepcopy(writer.manifest),
        "head": "a" * 64, "acknowledged_operations": {},
        "state": {
            "revision": 0,
            "positions": (
                {"A": {"symbol": held, "remaining": "1"}} if held else {}),
        },
    }
    writer._cut = lambda: copy.deepcopy(cut)
    owner = NativeQDPositionPins(writer=writer)
    clock = NativeUtcUpperBound(TestOnlyClock())
    feed = IEXFeed(["MSFT", "SPY"], clock=clock, max_age=5,
                   position_symbols=owner.current)
    return supervised.PinnedIEXWindow(feed=feed, owner=owner, clock=clock), cut


def message(symbol="MSFT", **changes):
    return {
        "symbol": symbol, "provider": "ALPACA_IEX",
        "timestamp": "2026-11-11T15:00:00Z",
        "paper_fill_authorized": False,
        "live_order_authorized": False, **changes,
    }


def result(rows=None):
    if rows is None:
        rows = {
            "MSFT": {"received": 1, "accepted": 1, "rejected": 0, "fresh_callbacks": 1},
            "SPY": {"received": 0, "accepted": 0, "rejected": 0, "fresh_callbacks": 0},
        }
    return {
        "authenticated": True, "subscribed": True, "reconnects": 0,
        "result": {"connection": "DISCONNECTED"},
        "per_symbol_quote_diagnostics": rows,
    }


def sample(window):
    window.clock.last_sample = None
    window.clock()


def assessment(window, data=None):
    return window.assess(
        result() if data is None else data,
        release_before={"installed": "R16"}, release_after={"installed": "R16"})


def test_genuine_type_and_exact_native_utc_binding_required():
    window, _ = fixture()
    assert window.roster == ("MSFT", "SPY")
    with pytest.raises(ValueError, match="OWNED_FEED_AND_NATIVE_UTC"):
        supervised.PinnedIEXWindow(
            feed=IEXFeed(["MSFT"], clock=time.time),
            owner=window.owner, clock=window.clock)
    with pytest.raises(ValueError, match="OWNED_FEED_AND_NATIVE_UTC"):
        supervised.PinnedIEXWindow(
            feed=window.feed, owner=object(), clock=window.clock)


def test_unchanged_owned_cut_stays_pinned_with_bounded_clock_poll():
    window, _ = fixture(held="MSFT")
    for _ in range(3):
        window.tick()
    assert window.pins == ("MSFT",)
    assert window.polls == 4
    assert window.clock.samples_verified >= 1


def test_new_position_or_financial_cut_conflict_disconnects_and_purges():
    window, cut = fixture()
    window.feed.connection = "CONNECTED"
    window.feed.authenticated = window.feed.subscribed = True
    window.feed.quotes["MSFT"] = {"bid": "private-price"}
    cut["state"]["revision"] = 1
    cut["state"]["positions"] = {"A": {"symbol": "MSFT", "remaining": "1"}}
    cut["head"] = "b" * 64
    with pytest.raises(ValueError, match="FINANCIAL_POSITION_CHANGED"):
        window.tick()
    assert window.feed.connection == "DISCONNECTED"
    assert window.feed.quotes == {}
    assert not window.feed.authenticated and not window.feed.subscribed


def test_position_cut_invalid_revokes_feed_without_preserving_quotes():
    window, cut = fixture()
    cut["state"]["revision"] = -1
    window.feed.quotes["MSFT"] = {"bid": "not-allowed-to-survive"}
    with pytest.raises(ValueError):
        window.tick()
    assert window.feed.quotes == {}


@pytest.mark.parametrize("mutation", [
    {"provider": "UNTRUSTED"},
    {"paper_fill_authorized": True},
    {"live_order_authorized": True},
    {"symbol": "AAPL"},
    {"timestamp": 999},
])
def test_callback_spoofing_cannot_enter_source_diagnostics(mutation):
    window, _ = fixture()
    with pytest.raises(ValueError, match="UNTRUSTED_CALLBACK"):
        window.on_quote(message(**mutation))
    assert window.received == {}
    assert window.feed.connection == "DISCONNECTED"


def test_callback_rotated_roster_cannot_retain_cache():
    window, _ = fixture()
    window.feed.roster_revision += 1
    window.feed.quotes["MSFT"] = {"bid": "discard"}
    with pytest.raises(ValueError, match="CALLBACK_ROSTER_CHANGED"):
        window.on_quote(message())
    assert window.feed.quotes == {}


def test_valid_observation_only_returns_counts_never_quotes():
    window, _ = fixture(held="MSFT")
    window.on_quote(message(bid="100", ask="101"))
    sample(window)
    report = assessment(window)
    assert report["fresh_callbacks_by_symbol"] == {"MSFT": 1}
    assert report["required_open_position_symbols"] == ["MSFT"]
    assert report["provider_authenticated_and_subscribed"]
    assert report["native_utc_samples_verified_in_window"] >= 1
    assert report["paper_start_authorized"] is False
    assert report["source_entitlement_accepted"] is False
    assert report["continuous_source_accepted"] is False
    assert "100" not in str(report) and "101" not in str(report)
    assert "2026-11-11T15" not in str(report)


@pytest.mark.parametrize("reason", [
    "wrong_callback_count", "missing_pin_callback", "provider_reconnected",
    "release_changed", "no_fresh", "unrefreshed_clock",
    "unsubscribed", "financial_grant", "invalid_counter",
])
def test_observation_with_missing_source_proof_refuses(reason):
    window, _ = fixture(held="MSFT" if reason == "missing_pin_callback" else None)
    data = result()
    if reason != "no_fresh" and reason != "missing_pin_callback":
        window.on_quote(message())
    if reason != "unrefreshed_clock":
        sample(window)
    if reason == "wrong_callback_count":
        data["per_symbol_quote_diagnostics"]["MSFT"]["fresh_callbacks"] = 2
    elif reason == "missing_pin_callback":
        data["per_symbol_quote_diagnostics"] = {
            "MSFT": {"received": 0, "accepted": 0, "rejected": 0, "fresh_callbacks": 0},
            "SPY": {"received": 1, "accepted": 1, "rejected": 0, "fresh_callbacks": 1},
        }
        window.on_quote(message("SPY"))
    elif reason == "provider_reconnected":
        data["reconnects"] = 1
    elif reason == "no_fresh":
        data["per_symbol_quote_diagnostics"] = {
            s: {"received": 0, "accepted": 0, "rejected": 0, "fresh_callbacks": 0}
            for s in ("MSFT", "SPY")
        }
    elif reason == "unsubscribed":
        data["subscribed"] = False
    elif reason == "financial_grant":
        data["paper_fill_authorized"] = True
    elif reason == "invalid_counter":
        data["per_symbol_quote_diagnostics"]["MSFT"]["accepted"] = -1
    release = {"installed": "R16"}
    after = {"installed": "WRONG"} if reason == "release_changed" else release
    with pytest.raises(ValueError):
        window.assess(data, release_before=release, release_after=after)


@pytest.mark.asyncio
async def test_bounded_data_only_session_clears_quotes_after_success(monkeypatch):
    window, _ = fixture(held="MSFT")
    monkeypatch.setattr(supervised, "require_original_selected_modules",
                        lambda: {"installed": "synthetic-selected-source"})
    calls = []
    async def fake_run(credentials, *, seconds, max_reconnects, stop, connect, on_fresh_quote):
        calls.append((seconds, max_reconnects, connect))
        window.feed.connection = "CONNECTED"
        window.feed.authenticated = window.feed.subscribed = True
        window.feed.quotes["MSFT"] = {"bid": "never-publish"}
        on_fresh_quote(message())
        sample(window)
        window.feed.disconnect()
        return result()
    monkeypatch.setattr(window.feed, "run", fake_run)
    out = await supervised.supervise_bounded_data_only(
        feed=window.feed, owner=window.owner, clock=window.clock,
        credentials=Credentials("synthetic-key", "synthetic-secret"),
        seconds=10, confirmed_scope=supervised.SCOPE)
    assert calls == [(10, 0, None)]
    assert out["fresh_callbacks_by_symbol"]["MSFT"] == 1
    assert not out["paper_start_authorized"]
    assert window.feed.quotes == {}
    assert window.feed.connection == "DISCONNECTED"


@pytest.mark.asyncio
async def test_watchdog_detects_financial_change_on_idle_socket(monkeypatch):
    window, cut = fixture()
    monkeypatch.setattr(supervised, "require_original_selected_modules",
                        lambda: {"installed": "synthetic-selected-source"})
    async def fake_run(credentials, *, seconds, max_reconnects, stop, connect, on_fresh_quote):
        cut["state"]["revision"] = 1
        cut["state"]["positions"] = {"A": {"symbol": "MSFT", "remaining": "1"}}
        cut["head"] = "b" * 64
        await stop.wait()
        return result()
    monkeypatch.setattr(window.feed, "run", fake_run)
    with pytest.raises(ValueError, match="WATCHDOG_REFUSED"):
        await supervised.supervise_bounded_data_only(
            feed=window.feed, owner=window.owner, clock=window.clock,
            credentials=Credentials("synthetic-key", "synthetic-secret"),
            seconds=10, confirmed_scope=supervised.SCOPE,
            poll_seconds=0.25)
    assert window.feed.quotes == {}
    assert window.feed.connection == "DISCONNECTED"


@pytest.mark.asyncio
async def test_original_selected_release_required_before_network(monkeypatch):
    window, _ = fixture()
    called = []
    async def never_run(*args, **kwargs):
        called.append(True)
        raise AssertionError("NETWORK_CALLED")
    monkeypatch.setattr(window.feed, "run", never_run)
    # In the test venv, the genuine R16 release verifier MUST refuse.
    with pytest.raises(ValueError, match="ORIGINAL_SELECTED_READONLY_PYTHON"):
        await supervised.supervise_bounded_data_only(
            feed=window.feed, owner=window.owner, clock=window.clock,
            credentials=Credentials("synthetic-key", "synthetic-secret"),
            seconds=10, confirmed_scope=supervised.SCOPE)
    assert not called


@pytest.mark.asyncio
async def test_scope_refused_before_any_network(monkeypatch):
    window, _ = fixture()
    for scope, seconds, poll in [
        ("TRADING", 10, 1.0), (supervised.SCOPE, 0, 1.0),
        (supervised.SCOPE, 10, 0.1), (supervised.SCOPE, True, 1.0),
    ]:
        with pytest.raises(ValueError, match="EXACT_DATA_ONLY_SCOPE"):
            await supervised.supervise_bounded_data_only(
                feed=window.feed, owner=window.owner, clock=window.clock,
                credentials=Credentials("synthetic-key", "synthetic-secret"),
                seconds=seconds, confirmed_scope=scope, poll_seconds=poll)


@pytest.mark.asyncio
async def test_in_flight_quote_after_watchdog_revocation_is_refused(monkeypatch):
    window, cut = fixture()
    monkeypatch.setattr(supervised, "require_original_selected_modules",
                        lambda: {"installed": "synthetic-selected-source"})

    async def fake_run(credentials, *, seconds, max_reconnects, stop, connect, on_fresh_quote):
        cut["state"]["revision"] = 1
        cut["state"]["positions"] = {"A": {"symbol": "MSFT", "remaining": "1"}}
        cut["head"] = "b" * 64
        await stop.wait()
        # Simulate a provider message already in-flight when the watchdog fires.
        on_fresh_quote(message())
        return result()

    monkeypatch.setattr(window.feed, "run", fake_run)
    with pytest.raises(ValueError, match="REVOKED_WINDOW_CALLBACK"):
        await supervised.supervise_bounded_data_only(
            feed=window.feed, owner=window.owner, clock=window.clock,
            credentials=Credentials("synthetic-key", "synthetic-secret"),
            seconds=10, confirmed_scope=supervised.SCOPE,
            poll_seconds=0.25)
    assert window.feed.connection == "DISCONNECTED"
    assert window.feed.quotes == {}
