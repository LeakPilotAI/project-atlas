"""Bounded owned-position IEX supervision; source-only and data-only.

A future accepted financial owner may supply a real NativeQDPositionPins cut.
Neither the bounded watchdog nor its quote diagnostics establish Alpaca rights,
financial clock leases, PAPER fills, trading permissions, or account inception.
No network or credentials are read at import or during construction.
"""
from __future__ import annotations

import asyncio
import secrets
import time
from collections import Counter

from app.investment.alpaca_iex import SYMBOL, Credentials, IEXFeed

from scripts.observation_runtime.atlas_r16_joint_ntp_iex_data_only import (
    NativeUtcUpperBound,
    require_original_selected_modules,
)
from scripts.observation_runtime.atlas_r16_owned_iex_shortlist import (
    NativeQDPositionPins,
    _invalidate_feed,
    require_current_pins,
)

SCHEMA = "ATLAS_R16_OWNED_PINNED_IEX_BOUNDED_SUPERVISION_V1"
SCOPE = "ALPACA_IEX_PINNED_POSITION_DATA_ONLY_NO_FINANCIAL_GRANT"


class PinnedIEXWindow:
    """Monitor actual source callback + position readback without forwarding prices."""

    def __init__(self, *, feed, owner, clock):
        if (type(feed) is not IEXFeed
                or type(owner) is not NativeQDPositionPins
                or type(clock) is not NativeUtcUpperBound
                or feed.clock is not clock
                or not 1 <= feed.max_age <= 5
                or not 1 <= len(feed.symbols) <= 30):
            raise ValueError("IEX_GENUINE_OWNED_FEED_AND_NATIVE_UTC_REQUIRED")
        self.feed, self.owner, self.clock = feed, owner, clock
        self.roster = tuple(feed.symbols)
        self.revision = feed.roster_revision
        self.pins = require_current_pins(feed=feed, owner=owner)
        self.received = Counter()
        self.polls = 0
        self.tick()  # Admission sample is NOT a during-window refresh.
        self.clock_samples_start = clock.samples_verified

    def refuse(self, reason):
        _invalidate_feed(self.feed, reason)
        raise ValueError(reason)

    def tick(self):
        """Read the real FS1/coordination cut; never treat roster ACK as position proof."""
        try:
            if (self.feed.roster_revision != self.revision
                    or tuple(self.feed.symbols) != self.roster
                    or self.feed.clock is not self.clock):
                self.refuse("IEX_SUPERVISED_ROSTER_OR_CLOCK_REPLACED")
            pins = require_current_pins(feed=self.feed, owner=self.owner)
            if pins != self.pins:
                self.refuse("IEX_SUPERVISED_FINANCIAL_POSITION_CHANGED")
            instant = self.clock()
            if type(instant) is not float:
                self.refuse("IEX_SUPERVISED_NATIVE_UTC_REQUIRED")
            self.polls += 1
        except BaseException:
            _invalidate_feed(self.feed, "IEX_SUPERVISED_OWNER_OR_CLOCK_LOST")
            raise

    def on_quote(self, event):
        """Data-only callback; no quote price is stored, returned or published."""
        if (type(event) is not dict
                or type(event.get("symbol")) is not str
                or event["symbol"] not in self.roster
                or event.get("provider") != "ALPACA_IEX"
                or type(event.get("timestamp")) is not str
                or event.get("paper_fill_authorized") is not False
                or event.get("live_order_authorized") is not False):
            self.refuse("IEX_SUPERVISED_UNTRUSTED_CALLBACK")
        if (self.feed.roster_revision != self.revision
                or tuple(self.feed.symbols) != self.roster
                or self.feed.clock is not self.clock):
            self.refuse("IEX_SUPERVISED_CALLBACK_ROSTER_CHANGED")
        # Native UTC is verified/cached by the existing R16 observer (<250 ms).
        # Native financial custody is polled separately, <=1 sec cadence:
        # callback bursts must NOT force thousands of disk readbacks per second.
        self.clock()
        self.received[event["symbol"]] += 1

    def assess(self, raw, *, release_before, release_after):
        self.tick()
        if (type(raw) is not dict
                or raw.get("authenticated") is not True
                or raw.get("subscribed") is not True
                or type(raw.get("reconnects")) is not int
                or raw["reconnects"] != 0
                or type(raw.get("result")) is not dict
                or raw["result"].get("connection") != "DISCONNECTED"
                or raw.get("paper_fill_authorized", False) is not False
                or raw.get("live_order_authorized", False) is not False
                or release_before != release_after):
            self.refuse("IEX_SUPERVISED_TRANSPORT_OR_RELEASE_NOT_ACCEPTED")
        diags = raw.get("per_symbol_quote_diagnostics")
        if (type(diags) is not dict or set(diags) != set(self.roster)
                or set(self.received) - set(self.roster)):
            self.refuse("IEX_SUPERVISED_SYMBOL_DIAGNOSTICS_INVALID")
        for symbol, row in diags.items():
            if (type(row) is not dict
                    or set(row) != {"received", "accepted", "rejected", "fresh_callbacks"}
                    or any(type(value) is not int or value < 0 for value in row.values())
                    or row["received"] != row["accepted"] + row["rejected"]
                    or row["fresh_callbacks"] != self.received[symbol]
                    or row["fresh_callbacks"] > row["accepted"]):
                self.refuse("IEX_SUPERVISED_CALLBACK_COUNT_MISMATCH")
        # Actual held positions without a fresh observed quote must not pass.
        if any(self.received[symbol] == 0 for symbol in self.pins):
            self.refuse("IEX_SUPERVISED_HELD_POSITION_QUOTE_UNAVAILABLE")
        if sum(self.received.values()) == 0:
            self.refuse("IEX_SUPERVISED_NO_FRESH_QUOTES")
        if self.clock.samples_verified <= self.clock_samples_start:
            self.refuse("IEX_SUPERVISED_NATIVE_CLOCK_NOT_REFRESHED")
        return {
            "schema": SCHEMA,
            "status": "BOUNDED_POSITION_SAFE_DATA_OBSERVED_NOT_FINANCIAL_SOURCE",
            "requested_symbols": list(self.roster),
            "required_open_position_symbols": list(self.pins),
            "native_position_readbacks": self.polls,
            "native_utc_samples_verified_in_window":
                self.clock.samples_verified - self.clock_samples_start,
            "fresh_callbacks_by_symbol": dict(sorted(self.received.items())),
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
        }


async def supervise_bounded_data_only(
        *, feed, owner, clock, credentials, seconds,
        confirmed_scope, connect=None, poll_seconds=1.0):
    """One 10..60-second, 0-reconnect session; no automatic background launcher.

    Native selected module identity is checked before any socket action.
    This remains unusable for financial PAPER until separately accepted rights,
    authority, and an installed native financial publisher are available.
    """
    if (confirmed_scope != SCOPE
            or type(credentials) is not Credentials
            or type(seconds) is not int or not 10 <= seconds <= 60
            or type(poll_seconds) is not float or not 0.25 <= poll_seconds <= 1.0):
        raise ValueError("IEX_SUPERVISOR_EXACT_DATA_ONLY_SCOPE_REQUIRED")
    before = require_original_selected_modules()
    window = PinnedIEXWindow(feed=feed, owner=owner, clock=clock)
    monotonic_start_ns = time.perf_counter_ns()
    stop = asyncio.Event()
    failure = []

    async def watchdog():
        while not stop.is_set():
            try:
                window.tick()
            except Exception as error:  # noqa: BLE001 - any watchdog fault must revoke this data-only window
                failure.append(error)
                stop.set()
                break
            try:
                await asyncio.wait_for(stop.wait(), timeout=poll_seconds)
            except TimeoutError:
                pass

    def on_quote(event):
        # The provider may deliver an in-flight frame after watchdog revocation.
        if stop.is_set():
            window.refuse("IEX_SUPERVISED_REVOKED_WINDOW_CALLBACK")
        window.on_quote(event)

    task = asyncio.create_task(watchdog())
    try:
        try:
            raw = await feed.run(
                credentials, seconds=seconds, max_reconnects=0,
                stop=stop, connect=connect, on_fresh_quote=on_quote)
        finally:
            stop.set()
            await task
        if failure:
            raise ValueError("IEX_SUPERVISED_WATCHDOG_REFUSED")
        result = window.assess(
            raw, release_before=before,
            release_after=require_original_selected_modules())
        monotonic_end_ns = time.perf_counter_ns()
        if monotonic_end_ns <= monotonic_start_ns:
            window.refuse("IEX_SUPERVISED_MONOTONIC_WINDOW_INVALID")
        return {
            **result,
            "bounded_window_nonce": secrets.token_hex(16),
            "bounded_requested_seconds": seconds,
            "bounded_window_start_monotonic_ns": monotonic_start_ns,
            "bounded_window_end_monotonic_ns": monotonic_end_ns,
        }
    finally:
        stop.set()
        if not task.done():
            await task
        # A successful observational window still cannot retain executable prices.
        _invalidate_feed(feed, "IEX_SUPERVISED_BOUNDED_DATA_ONLY_CLOSED")

class BoundedIEXMultiSessionAudit:
    """In-memory correlation of separate bounded data-only observations.

    It cannot issue leases, verify external market-data rights, attest financial
    custody, or prove that data was continuously available BETWEEN sockets.
    Nonces and local monotonic times only detect obvious same-process replay;
    they are NOT cryptographic evidence or native issuer signatures.
    """

    def __init__(self, *, max_sessions=12, max_gap_seconds=120):
        if (type(max_sessions) is not int or not 2 <= max_sessions <= 16
                or type(max_gap_seconds) is not int
                or not 0 <= max_gap_seconds <= 120):
            raise ValueError("IEX_MULTIWINDOW_EXACT_OFFLINE_BOUNDS_REQUIRED")
        self.max_sessions = max_sessions
        self.max_gap_seconds = max_gap_seconds
        self.sessions = []
        self.nonces = set()
        self.pins = None
        self.failed = False

    def _refuse(self, code):
        # No receipt is emitted from an invalid chain; never silently skip a
        # bad window and continue as if reliability were uninterrupted.
        self.failed = True
        self.sessions.clear()
        self.nonces.clear()
        raise ValueError(code)

    def append(self, report):
        if self.failed or len(self.sessions) >= self.max_sessions:
            self._refuse("IEX_MULTIWINDOW_CLOSED_OR_OVER_CAPACITY")
        if type(report) is not dict:
            self._refuse("IEX_MULTIWINDOW_EXACT_REPORT_REQUIRED")
        for key, expected in (
            ("schema", SCHEMA),
            ("status", "BOUNDED_POSITION_SAFE_DATA_OBSERVED_NOT_FINANCIAL_SOURCE"),
            ("provider_authenticated_and_subscribed", True),
            ("socket_closed", True),
            ("provider_reconnects", 0),
            ("source_entitlement_accepted", False),
            ("continuous_source_accepted", False),
            ("financial_clock_lease_accepted", False),
            ("financial_writer_lease_accepted", False),
            ("paper_start_authorized", False),
            ("live_trading_authorized", False),
            ("orders_created", 0),
        ):
            if key not in report or type(report[key]) is not type(expected) or report[key] != expected:
                self._refuse("IEX_MULTIWINDOW_FINANCIAL_OR_SOURCE_PROOF_REFUSED")
        nonce = report.get("bounded_window_nonce")
        requested = report.get("bounded_requested_seconds")
        start = report.get("bounded_window_start_monotonic_ns")
        end = report.get("bounded_window_end_monotonic_ns")
        pins = report.get("required_open_position_symbols")
        symbols = report.get("requested_symbols")
        callbacks = report.get("fresh_callbacks_by_symbol")
        samples = report.get("native_utc_samples_verified_in_window")
        readbacks = report.get("native_position_readbacks")
        if (type(nonce) is not str or len(nonce) != 32
                or any(char not in "0123456789abcdef" for char in nonce)
                or nonce in self.nonces
                or type(requested) is not int or not 10 <= requested <= 60
                or type(start) is not int or type(end) is not int
                or not 0 < start < end
                or not (requested - 1) * 1_000_000_000 <= end - start
                   <= (requested + 10) * 1_000_000_000
                or type(pins) is not list
                or type(symbols) is not list or not 1 <= len(symbols) <= 30
                or any(type(s) is not str or SYMBOL.fullmatch(s) is None for s in symbols)
                or len(set(symbols)) != len(symbols)
                or any(type(s) is not str or s not in symbols for s in pins)
                or len(set(pins)) != len(pins)
                or type(callbacks) is not dict or set(callbacks) != set(symbols)
                or any(type(v) is not int or not 0 <= v <= 10_000_000
                       for v in callbacks.values())
                or sum(callbacks.values()) == 0
                or any(callbacks[s] == 0 for s in pins)
                or type(samples) is not int or not 1 <= samples <= 100_000
                or type(readbacks) is not int or not 2 <= readbacks <= 100_000):
            self._refuse("IEX_MULTIWINDOW_INCOMPLETE_OBSERVATION_REQUIRED")
        if self.pins is not None and tuple(pins) != self.pins:
            self._refuse("IEX_MULTIWINDOW_POSITION_SCOPE_CHANGED")
        if self.sessions:
            previous_end = self.sessions[-1]["end"]
            if start < previous_end or start - previous_end > self.max_gap_seconds * 1_000_000_000:
                self._refuse("IEX_MULTIWINDOW_GAP_OVERLAP_OR_REPLAY")
        else:
            self.pins = tuple(pins)
        self.nonces.add(nonce)
        self.sessions.append({
            "start": start, "end": end,
            "symbols": tuple(symbols),
            "fresh": dict(callbacks),
            "samples": samples,
            "readbacks": readbacks,
        })
        return {
            "schema": "ATLAS_R16_MULTIWINDOW_DATA_ONLY_COLLECTION_V1",
            "bounded_windows_collected": len(self.sessions),
            "continuous_source_accepted": False,
            "paper_start_authorized": False,
            "live_trading_authorized": False,
        }

    def summarize(self):
        if self.failed or len(self.sessions) < 2:
            self._refuse("IEX_MULTIWINDOW_AT_LEAST_TWO_VALID_WINDOWS_REQUIRED")
        total_ns = sum(s["end"] - s["start"] for s in self.sessions)
        gaps = [self.sessions[i]["start"] - self.sessions[i - 1]["end"]
                for i in range(1, len(self.sessions))]
        visited = {s for session in self.sessions for s in session["symbols"]}
        fresh = {s for session in self.sessions
                 for s, count in session["fresh"].items() if count > 0}
        return {
            "schema": "ATLAS_R16_MULTIWINDOW_DATA_ONLY_RELIABILITY_RESEARCH_V1",
            "status": "MULTIPLE_BOUNDED_OBSERVATIONS_NOT_CONTINUOUS_CUSTODY",
            "successful_bounded_windows": len(self.sessions),
            "separately_observed_seconds": round(total_ns / 1_000_000_000, 3),
            "unobserved_gap_seconds": round(sum(gaps) / 1_000_000_000, 3),
            "max_unobserved_gap_seconds": round(max(gaps) / 1_000_000_000, 3),
            "unique_symbols_requested_over_windows": len(visited),
            "unique_symbols_with_at_least_one_fresh_callback": len(fresh),
            "pinned_position_symbols_consistent": list(self.pins),
            "total_native_utc_verified_samples": sum(s["samples"] for s in self.sessions),
            "total_custody_readbacks": sum(s["readbacks"] for s in self.sessions),
            "report_receipts_not_cryptographically_authenticated": True,
            "unobserved_gaps_present": True,
            "source_entitlement_accepted": False,
            "continuous_source_accepted": False,
            "financial_writer_lease_accepted": False,
            "financial_clock_lease_accepted": False,
            "paper_start_authorized": False,
            "live_trading_authorized": False,
            "orders_created": 0,
        }
