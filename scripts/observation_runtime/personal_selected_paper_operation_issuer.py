"""Two-lane selected-native PAPER operation issuer; never an account/Start issuer.

A financial *operation* is only admitted inside an already-established,
genuinely selected and installed native R17+ session with both authentic
sources and an independently armed durable SHUTDOWN_FLATTEN Stop owner.
Original Windows Job and PROCESS handles, native account FS1/FS3 publisher
acknowledgements, native independent clock, current Alpaca IEX L1 execution
authority and Hyperliquid operational archive are rechecked in one bounded
synchronous context.

This module CANNOT start a runtime, commission accounts, create a financial
lease before Stop is bound, create credentials or submit broker/venue orders.
A real first-start financial issuer and source-rights acceptance are separate
prerequisites. Do not use as financial gate acceptance by importing it.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from threading import Lock

from app.services.hyperliquid_current_producer import HyperliquidCurrentProducer
from app.services.paper_financial_replay import body, digest, strict
from app.services.personal_installed_stop_owner import PersonalInstalledPaperStopOwner
from app.services.quality_dips_iex_input import IEXPaperQuotes

from scripts.observation_runtime.personal_local_authority import (
    NativePersonalOperatorAuthority,
)
from scripts.observation_runtime.personal_native_selected_owned_job_preflight import (
    RetainedSelectedNativeOwnerPreflight,
)
from scripts.observation_runtime.personal_version_safe_release_clock import (
    NativeVersionSafePaperOperatorClock,
    require_version_safe_release_digest,
)

SCHEMA = "ATLAS_SELECTED_NATIVE_TWO_LANE_PAPER_OPERATION_LEASE_V1"
LANES = frozenset(("QUALITY_DIPS", "HYPERLIQUID"))
SOURCE_SCOPES = frozenset((*LANES, "BOTH"))


class PaperSourceUnavailable(ValueError):
    """A proven lane-local READ-ONLY feed refusal before financial dispatch."""


class NativeSelectedPaperOperationIssuer:
    """No mutable grants or startup path; a per-operation live capability."""

    def __init__(self, *, owner, operator, clock, stop_owner,
                 qd_source, hl_source, qd, perp):
        # Keep these EXACT class requirements. Inherited or duck-typed ports
        # may otherwise claim a financial source/Job/Stop acceptance they lack.
        if (type(owner) is not RetainedSelectedNativeOwnerPreflight
                or type(operator) is not NativePersonalOperatorAuthority
                or type(clock) is not NativeVersionSafePaperOperatorClock
                or type(stop_owner) is not PersonalInstalledPaperStopOwner
                or type(qd_source) is not IEXPaperQuotes
                or type(hl_source) is not HyperliquidCurrentProducer):
            raise ValueError("SELECTED_PAPER_EXACT_NATIVE_JOB_OPERATOR_SOURCES_STOP_REQUIRED")
        if (owner._phase != "INITIAL_READBACK_ONLY"
                or owner.release_digest != operator.enrollment["release_digest"]
                or owner.release_digest != hl_source.enrollment["release_digest"]
                or operator.enrollment != qd
                or hl_source.enrollment != perp
                or operator.clock is not clock
                or hl_source.clock is not clock
                or qd_source.authority is None
                or qd_source.session_id != stop_owner.session_id
                or hl_source.execution_domain != "OPERATIONAL"
                or operator.accounts != {
                    "QUALITY_DIPS": digest(qd),
                    "HYPERLIQUID": digest(perp),
                }
                or stop_owner._runtime.clock is not clock
                or stop_owner._runtime.installation is not stop_owner._installation
                or stop_owner._runtime.grant.get("session_id") != stop_owner.session_id):
            raise ValueError("SELECTED_PAPER_ONE_NATIVE_RELEASE_TWO_ACCOUNTS_STOP_SCOPE_REQUIRED")
        self.owner, self.operator, self.clock = owner, operator, clock
        self.stop_owner, self.qd_source, self.hl_source = stop_owner, qd_source, hl_source
        self.qd, self.perp = strict(body(qd)), strict(body(perp))
        self._account_pins = digest([qd, perp])
        self._ports = (owner, operator, clock, stop_owner, qd_source, hl_source)
        self._session = stop_owner.session_id
        self._revoke = False
        self._lease_lock = Lock()

    def revoke(self):
        self._revoke = True

    def _verify_base(self, *, allow_armed=False):
        if (self._revoke
                or any(a is not b for a, b in zip(
                    (self.owner, self.operator, self.clock,
                     self.stop_owner, self.qd_source, self.hl_source),
                    self._ports, strict=True))
                or digest([self.qd, self.perp]) != self._account_pins
                or self.owner._phase != "INITIAL_READBACK_ONLY"
                or self.owner.release_digest != self.qd["release_digest"]
                or self.owner.release_digest != self.perp["release_digest"]
                or self.stop_owner.session_id != self._session
                or self.stop_owner._used
                or (self.stop_owner._runtime.entry_closed.is_set()
                    and not allow_armed)
                or (allow_armed and (
                    self.stop_owner._runtime._stop_first_state != 'ARMED'
                    or not self.stop_owner._runtime.entry_closed.is_set()
                    or self.stop_owner._runtime.state != 'PAUSED'))
                or self.stop_owner._runtime.uncertain
                or self.stop_owner._runtime.grant.get("test_only") is True
                or self.stop_owner._runtime.state not in ("RUNNING", "PAUSED")):
            raise ValueError("SELECTED_PAPER_FINANCIAL_OPERATION_LEASE_REVOKED")
        # Native release identity is not inferred from a local JSON flag.
        # Both this explicit clock source and owner use the exact active
        # version-safe installed selector and its original Windows handles.
        require_version_safe_release_digest(
            clock=self.clock, runtime_id=self.operator.runtime_id,
            release_digest=self.owner.release_digest,
        )
        self.owner.require_exact_roster(qd=self.qd, perp=self.perp)
        self.operator.activation("AUTO_PAPER")
        if (self.operator.accounts != {
                "QUALITY_DIPS": digest(self.qd),
                "HYPERLIQUID": digest(self.perp),
            }
                or self.qd_source.session_id != self._session
                or self.qd_source.authority is None
                or self.hl_source.execution_domain != "OPERATIONAL"
                or self.hl_source.clock is not self.clock
                or self.stop_owner.verify_session() is not True):
            raise ValueError("SELECTED_PAPER_CURRENT_OPERATOR_OR_STOP_REVOKED")
        return True

    def _verify_sources(self, *, qd_instrument=None, lane="BOTH",
                        allow_armed=False):
        if type(lane) is not str or lane not in SOURCE_SCOPES:
            raise ValueError("SELECTED_PAPER_EXACT_FINANCIAL_LANE_REQUIRED")
        self._verify_base(allow_armed=allow_armed)
        instrument, quote, cut = None, None, None
        if lane in ("QUALITY_DIPS", "BOTH"):
            instrument = strict(body(qd_instrument))
            if (type(qd_instrument) is not dict
                    or not {"symbol", "instrument_id", "asset_class", "currency"}
                    <= set(qd_instrument)
                    or instrument["asset_class"] not in ("STOCK", "ETF")
                    or instrument["currency"] != "USD"):
                raise ValueError("SELECTED_PAPER_EXACT_INSTRUMENT_REQUIRED")
            # IEX freshness, exchange calendar, entitlement and session
            # acceptance apply only to the stock/ETF lane. No cached or
            # research-only quote can authorize Quality Dips entries.
            try:
                quote = self.qd_source.quote(instrument)
            except (ValueError, OSError, TimeoutError, KeyError) as exc:
                self._verify_base(allow_armed=allow_armed)
                raise PaperSourceUnavailable(
                    "SELECTED_PAPER_QD_CURRENT_EXECUTION_FEED_UNAVAILABLE"
                ) from exc
            if (type(quote) is not dict or quote.get("schema") != "QD_AUTO_L1_V1"
                    or quote.get("symbol") != instrument["symbol"]
                    or quote.get("instrument_id") != instrument["instrument_id"]
                    or quote.get("market_status") != "TRADING"
                    or quote.get("delay_status") != "REALTIME"
                    or quote.get("connection_status") != "CONNECTED"):
                self._verify_base(allow_armed=allow_armed)
                raise PaperSourceUnavailable(
                    "SELECTED_PAPER_GENUINE_FRESH_QD_L1_REQUIRED")
        if lane in ("HYPERLIQUID", "BOTH"):
            # The perpetual lane is independently available 24/7; it never
            # queries IEX or requires an equity exchange OPEN calendar.
            try:
                self.hl_source._verify()
                cut = self.hl_source.read_cut()
            except (ValueError, OSError, TimeoutError, KeyError) as exc:
                self._verify_base(allow_armed=allow_armed)
                raise PaperSourceUnavailable(
                    "SELECTED_PAPER_HL_CURRENT_OPERATIONAL_SOURCE_UNAVAILABLE"
                ) from exc
            if type(cut) is not dict:
                self._verify_base(allow_armed=allow_armed)
                raise PaperSourceUnavailable(
                    "SELECTED_PAPER_GENUINE_FRESH_HL_OPERATIONAL_CUT_REQUIRED")
        self._verify_base(allow_armed=allow_armed)
        return instrument, quote, cut

    def verify_prepared_for_start(self, *, qd_instrument=None, lane="BOTH"):
        """Original native owner/source/Stop proof while entry remains CLOSED.

        Never starts a session, releases entry, or produces reusable finance
        authorization. The runtime controls the eventual atomic release.
        """
        runtime = self.stop_owner._runtime
        if (runtime._stop_first_state != 'ARMED'
                or not runtime.entry_closed.is_set()
                or runtime.state != 'PAUSED'
                or runtime._stop_first_issuer is not None
                or self.stop_owner._used):
            raise ValueError('SELECTED_PAPER_STOP_FIRST_NOT_SAFELY_ARMED')
        self._verify_sources(qd_instrument=qd_instrument, lane=lane,
                             allow_armed=True)
        return time.monotonic()

    @contextmanager
    def lease(self, *, qd_instrument=None, lane="BOTH"):
        """Financial-operation identity check, not an order/Start capability."""
        if not self._lease_lock.acquire(blocking=False):
            raise ValueError("SELECTED_PAPER_FINANCIAL_OPERATION_ALREADY_ACTIVE")
        try:
            with self._retain_operation_lease(
                    qd_instrument=qd_instrument, lane=lane) as lease:
                yield lease
        finally:
            self._lease_lock.release()

    @contextmanager
    def _retain_operation_lease(self, *, qd_instrument, lane):
        instrument, quote, cut = self._verify_sources(
            qd_instrument=qd_instrument, lane=lane)
        issuer, pins, session = self, self._ports, self._session
        issued_at = time.monotonic()
        sealed_instrument = strict(body(instrument))
        sealed_quote = strict(body(quote))
        sealed_hl_cut = strict(body(cut))
        live = [True]

        class Lease:
            def check(self):
                now = time.monotonic()
                if (not live[0] or issuer._revoke
                        or now < issued_at or now - issued_at > 5
                        or issuer._ports != pins or issuer._session != session):
                    return False
                try:
                    now_instrument, now_quote, now_cut = issuer._verify_sources(
                        qd_instrument=sealed_instrument, lane=lane)
                    return (now_instrument == sealed_instrument
                            and now_quote == sealed_quote
                            and now_cut == sealed_hl_cut)
                except (ValueError, OSError, TimeoutError, KeyError, TypeError, AttributeError):
                    return False

            @property
            def receipt(self):
                if self.check() is not True:
                    raise ValueError("SELECTED_PAPER_REVOKED_LEASE_RECEIPT_REFUSED")
                return {
                    "schema": SCHEMA,
                    "session_id": session,
                    "source_lane": lane,
                    "qd_instrument_id": (
                        sealed_instrument["instrument_id"]
                        if sealed_instrument is not None else None),
                    "financial_operational_source_and_stop_rechecked": True,
                    "paper_only": True,
                    "live_trading_authorized": False,
                    "external_broker_orders_authorized": False,
                    "account_inception_authorized": False,
                    "financial_startup_authorized": False,
                    "operating_gate_independently_accepted": False,
                }

        lease = Lease()
        try:
            if lease.check() is not True:
                raise ValueError("SELECTED_PAPER_OPERATION_LEASE_CHANGED_BEFORE_USE")
            yield lease
            if lease.check() is not True:
                raise ValueError("SELECTED_PAPER_OPERATION_LEASE_CHANGED_AFTER_USE")
        finally:
            live[0] = False
