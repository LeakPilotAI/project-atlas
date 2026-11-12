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
    assert out["bounded_requested_seconds"] == 10
    assert len(out["bounded_window_nonce"]) == 32
    assert out["bounded_window_start_monotonic_ns"] < out["bounded_window_end_monotonic_ns"]
    # A zero-duration synthetic provider stub is NOT evidence of a real soak.
    with pytest.raises(ValueError, match="INCOMPLETE_OBSERVATION"):
        supervised.BoundedIEXMultiSessionAudit().append(out)
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


def multiwindow_report(*, nonce="a" * 32, start=10**12, held=("MSFT",),
                       symbols=("MSFT", "SPY"), callbacks=None):
    """Fabricated no-network evidence for schema/replay refusal tests ONLY."""
    if callbacks is None:
        callbacks = {"MSFT": 2, "SPY": 0}
    return {
        "schema": supervised.SCHEMA,
        "status": "BOUNDED_POSITION_SAFE_DATA_OBSERVED_NOT_FINANCIAL_SOURCE",
        "requested_symbols": list(symbols),
        "required_open_position_symbols": list(held),
        "native_position_readbacks": 11,
        "native_utc_samples_verified_in_window": 12,
        "fresh_callbacks_by_symbol": callbacks,
        "provider_authenticated_and_subscribed": True,
        "provider_reconnects": 0,
        "socket_closed": True,
        "source_entitlement_accepted": False,
        "continuous_source_accepted": False,
        "financial_clock_lease_accepted": False,
        "financial_writer_lease_accepted": False,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
        "orders_created": 0,
        "bounded_window_nonce": nonce,
        "bounded_requested_seconds": 10,
        "bounded_window_start_monotonic_ns": start,
        "bounded_window_end_monotonic_ns": start + 10_000_000_000,
    }


def test_bounded_multisession_audit_distinguishes_observed_time_from_gaps():
    audit = supervised.BoundedIEXMultiSessionAudit(max_sessions=3, max_gap_seconds=5)
    first = multiwindow_report()
    second = multiwindow_report(nonce="b" * 32, start=first["bounded_window_end_monotonic_ns"] + 2_000_000_000)
    assert audit.append(first)["bounded_windows_collected"] == 1
    assert audit.append(second)["bounded_windows_collected"] == 2
    summary = audit.summarize()
    assert summary["successful_bounded_windows"] == 2
    assert summary["separately_observed_seconds"] == 20
    assert summary["unobserved_gap_seconds"] == 2
    assert summary["max_unobserved_gap_seconds"] == 2
    assert summary["unique_symbols_requested_over_windows"] == 2
    assert summary["unique_symbols_with_at_least_one_fresh_callback"] == 1
    assert summary["pinned_position_symbols_consistent"] == ["MSFT"]
    assert summary["total_native_utc_verified_samples"] == 24
    assert summary["total_custody_readbacks"] == 22
    assert summary["report_receipts_not_cryptographically_authenticated"]
    assert summary["unobserved_gaps_present"]
    assert not summary["source_entitlement_accepted"]
    assert not summary["continuous_source_accepted"]
    assert not summary["paper_start_authorized"]


def test_multiwindow_allows_roster_research_rotation_but_preserves_held_symbols():
    audit = supervised.BoundedIEXMultiSessionAudit()
    first = multiwindow_report()
    second = multiwindow_report(
        nonce="b" * 32, start=first["bounded_window_end_monotonic_ns"],
        symbols=("MSFT", "AAPL"),
        callbacks={"MSFT": 1, "AAPL": 1})
    audit.append(first)
    audit.append(second)
    assert audit.summarize()["unique_symbols_requested_over_windows"] == 3
    assert audit.summarize()["unique_symbols_with_at_least_one_fresh_callback"] == 2


@pytest.mark.parametrize("damage", [
    "replay_nonce", "overlap", "gap", "foreign_pins", "held_quote_missing",
    "financial_fill", "financial_writer", "continuous_grant", "license_grant",
    "wrong_status", "not_connected", "nonmonotonic", "fake_duration",
    "invalid_quote_count", "wrong_symbols", "untrusted_symbol_object",
    "untrusted_pin_object", "clock_sample_missing", "custody_readback_missing",
    "forged_order", "boolean_reconnects", "duplicate_symbols", "bad_nonce",
])
def test_multiwindow_bad_second_session_revokes_entire_evidence_chain(damage):
    audit = supervised.BoundedIEXMultiSessionAudit(max_gap_seconds=5)
    first = multiwindow_report()
    audit.append(first)
    bad = multiwindow_report(
        nonce="b" * 32, start=first["bounded_window_end_monotonic_ns"] + 1_000_000_000)
    if damage == "replay_nonce":
        bad["bounded_window_nonce"] = first["bounded_window_nonce"]
    elif damage == "overlap":
        bad["bounded_window_start_monotonic_ns"] = first["bounded_window_start_monotonic_ns"] + 1
        bad["bounded_window_end_monotonic_ns"] = bad["bounded_window_start_monotonic_ns"] + 10_000_000_000
    elif damage == "gap":
        bad["bounded_window_start_monotonic_ns"] += 6_000_000_000
        bad["bounded_window_end_monotonic_ns"] += 6_000_000_000
    elif damage == "foreign_pins":
        bad["required_open_position_symbols"] = ["SPY"]
    elif damage == "held_quote_missing":
        bad["fresh_callbacks_by_symbol"] = {"MSFT": 0, "SPY": 2}
    elif damage == "financial_fill":
        bad["paper_start_authorized"] = True
    elif damage == "financial_writer":
        bad["financial_writer_lease_accepted"] = True
    elif damage == "continuous_grant":
        bad["continuous_source_accepted"] = True
    elif damage == "license_grant":
        bad["source_entitlement_accepted"] = True
    elif damage == "wrong_status":
        bad["status"] = "FINANCIAL_READY"
    elif damage == "not_connected":
        bad["provider_authenticated_and_subscribed"] = False
    elif damage == "nonmonotonic":
        bad["bounded_window_end_monotonic_ns"] = bad["bounded_window_start_monotonic_ns"]
    elif damage == "fake_duration":
        bad["bounded_window_end_monotonic_ns"] = bad["bounded_window_start_monotonic_ns"] + 100
    elif damage == "invalid_quote_count":
        bad["fresh_callbacks_by_symbol"]["MSFT"] = -1
    elif damage == "wrong_symbols":
        bad["fresh_callbacks_by_symbol"]["AAPL"] = 1
    elif damage == "untrusted_symbol_object":
        bad["requested_symbols"] = [{"symbol": "MSFT"}]
    elif damage == "untrusted_pin_object":
        bad["required_open_position_symbols"] = [{"symbol": "MSFT"}]
    elif damage == "clock_sample_missing":
        bad["native_utc_samples_verified_in_window"] = 0
    elif damage == "custody_readback_missing":
        bad["native_position_readbacks"] = 0
    elif damage == "forged_order":
        bad["orders_created"] = 1
    elif damage == "boolean_reconnects":
        bad["provider_reconnects"] = False
    elif damage == "duplicate_symbols":
        bad["requested_symbols"] = ["MSFT", "MSFT"]
    elif damage == "bad_nonce":
        bad["bounded_window_nonce"] = "BOGUS"
    with pytest.raises(ValueError, match="IEX_MULTIWINDOW"):
        audit.append(bad)
    assert audit.failed and audit.sessions == [] and audit.nonces == set()
    with pytest.raises(ValueError, match="IEX_MULTIWINDOW"):
        audit.summarize()


def test_multiwindow_requires_two_windows_and_enforces_capacity():
    audit = supervised.BoundedIEXMultiSessionAudit(max_sessions=2)
    with pytest.raises(ValueError, match="AT_LEAST_TWO"):
        audit.summarize()
    assert audit.failed
    new = supervised.BoundedIEXMultiSessionAudit(max_sessions=2)
    one = multiwindow_report()
    new.append(one)
    new.append(multiwindow_report(
        nonce="b" * 32, start=one["bounded_window_end_monotonic_ns"]))
    with pytest.raises(ValueError, match="OVER_CAPACITY"):
        new.append(multiwindow_report(
            nonce="c" * 32, start=one["bounded_window_end_monotonic_ns"] + 10_000_000_000))
    assert new.failed


@pytest.mark.parametrize("max_sessions,max_gap_seconds", [
    (1, 120), (17, 120), (True, 120), (4, 121), (4, -1), (4, False),
])
def test_multiwindow_offline_resource_bounds_never_auto_start(max_sessions, max_gap_seconds):
    with pytest.raises(ValueError, match="EXACT_OFFLINE_BOUNDS"):
        supervised.BoundedIEXMultiSessionAudit(
            max_sessions=max_sessions, max_gap_seconds=max_gap_seconds)
