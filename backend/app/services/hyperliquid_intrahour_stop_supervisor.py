"""Verified one-shot, PRE-funding native PAPER Stop supervisor.

SOURCE ONLY, NOT INSTALLED or a financial commissioning issuer. This is a
risk-reducing supervisor over a *previously accepted* genuine local financial
Stop owner. The existing two-account Stop owns actual native ACKs and drain.
Time boundaries cannot prove a position was ever flat at an exchange event;
this code never assumes zero funding, verifies a fee tier, or grants entries.
"""
from __future__ import annotations

from app.services.hyperliquid_forward_flat_paper_policy import (
    GUARD_AFTER_FUNDING_SECONDS,
    GUARD_BEFORE_FUNDING_SECONDS,
    HOUR,
)
from app.services.personal_installed_stop_owner import (
    PersonalInstalledPaperStopOwner,
)

SCHEMA = "ATLAS_SELECTED_NATIVE_HL_ONE_SHOT_PRE_FUNDING_STOP_V1"
STOP_AHEAD_SECONDS = GUARD_BEFORE_FUNDING_SECONDS + 180
CLOCK_MARGIN_SECONDS = 2


def _int_time(value):
    if type(value) is not int or value < 1_600_000_000:
        raise ValueError("HL_PRE_FUNDING_GENUINE_INTEGER_UTC_REQUIRED")
    return value


class NativeIntrahourPaperStopSupervisor:
    """Actual shared STOP owner for an HL-exposed lane, including BOTH.

    In BOTH mode a single original SHUTDOWN_FLATTEN must stop BOTH lanes;
    neither QD nor HL may keep trading after the funding cutoff.
    """

    def __init__(self, *, owner):
        if type(owner) is not PersonalInstalledPaperStopOwner:
            raise ValueError("HL_PRE_FUNDING_REAL_SELECTED_NATIVE_STOP_OWNER_REQUIRED")
        runtime = owner._runtime
        if (
            runtime._stop_first_state != "RELEASED"
            or runtime._stop_first_initial_source_lane
               not in ("HYPERLIQUID", "BOTH")
            or runtime.state != "RUNNING"
            or runtime.entry_closed.is_set() or runtime.uncertain
            or owner._used or owner.verify_session() is not True
            or owner._runtime.installation is not owner._installation
            or not callable(runtime.clock)
        ):
            raise ValueError("HL_PRE_FUNDING_HL_EXPOSED_STOP_FIRST_NOT_ACCEPTED")
        self.owner = owner
        self.runtime = runtime
        self.clock = runtime.clock
        self.session_id = owner.session_id
        self.source_lane = runtime._stop_first_initial_source_lane
        self.terminal = False
        self._last_time = None
        try:
            self.initial_hour = _int_time(self.clock()) // HOUR
        except BaseException:
            self._refuse_unverifiable()
            raise

    def _refuse_unverifiable(self):
        # A proof failure is not an ordinary no-signal event. In particular,
        # an invalid UTC after Start must not leave the PAPER run continuing
        # without the mandatory time-based Stop.
        self.terminal = True
        self.runtime.entry_closed.set()
        self.runtime.uncertain = True
        if self.runtime.state in ("RUNNING", "PAUSED"):
            self.runtime.state = "STOP_INCOMPLETE"

    def _require_same_owner(self):
        r, owner = self.runtime, self.owner
        if self.terminal:
            raise ValueError("HL_PRE_FUNDING_STOP_OWNER_CHANGED_OR_REVOKED")
        if (
            owner._runtime is not r
            or owner.session_id != self.session_id
            or r.clock is not self.clock
            or r._stop_first_state != "RELEASED"
            or r._stop_first_initial_source_lane != self.source_lane
            or self.source_lane not in ("HYPERLIQUID", "BOTH")
            or r.state != "RUNNING"
            or r.uncertain or r.entry_closed.is_set() or owner._used
            or owner.verify_session() is not True
        ):
            self._refuse_unverifiable()
            raise ValueError("HL_PRE_FUNDING_STOP_OWNER_CHANGED_OR_REVOKED")

    def _time(self):
        try:
            value = _int_time(self.clock())
            if self._last_time is not None and value < self._last_time:
                raise ValueError("HL_PRE_FUNDING_UTC_ROLLBACK")
        except BaseException:
            self._refuse_unverifiable()
            raise
        self._last_time = value
        return value

    def entry_window(self):
        """Only independent admission check; NEVER grants any financial entry."""
        self._require_same_owner()
        now = self._time()
        beginning = now // HOUR * HOUR
        next_hour = beginning + HOUR
        return (now >= beginning + GUARD_AFTER_FUNDING_SECONDS + CLOCK_MARGIN_SECONDS
                and now + 1200 + CLOCK_MARGIN_SECONDS
                < next_hour - GUARD_BEFORE_FUNDING_SECONDS
                and now // HOUR == self.initial_hour)

    def tick(self):
        """Once-only genuine Stop at T-8m; bounded failure is terminal.

        The *actual* native Stop receipt is checked from the original ledger.
        Never return FLAT based on a timestamp alone. On uncertainty the
        original financial entry latch remains closed, with no retry.
        """
        self._require_same_owner()
        now = self._time()
        next_hour = (self.initial_hour + 1) * HOUR
        # If the owner fails to tick before the funding boundary, still
        # attempt the ONE reducing Stop to protect remaining positions.
        # A resulting late flat receipt must never count as pre-funding proof.
        late = now // HOUR != self.initial_hour
        seconds_left = next_hour - now
        if seconds_left > STOP_AHEAD_SECONDS:
            return {
                "schema": SCHEMA,
                "status": "STILL_SUPERVISING_NO_FINANCIAL_PERMISSION",
                "remaining_until_next_utc_funding_seconds": seconds_left,
                "new_entries_authorized": False,
                "funding_cost_assumed_zero": False,
                "paper_start_authorized": False,
            }
        # This latch is intentional even if the native owner's Stop fails.
        self.runtime.entry_closed.set()
        self.terminal = True
        try:
            if self.owner.verify_session() is not True:
                raise ValueError("HL_PRE_FUNDING_NATIVE_STOP_SESSION_REVOKED")
            receipt = self.owner.request_stop("SHUTDOWN_FLATTEN")
            after = self._time()
            if (
                type(receipt) is not dict
                or receipt.get("schema") != "QD_CONTROL_STOP_V1"
                or receipt.get("phase") != "FINISHED"
                or type(receipt.get("outcome")) is not dict
                or receipt["outcome"].get("status") != "FLATTENED"
                or receipt["outcome"].get("position_state") != "FLAT"
                or receipt["outcome"].get("process_shutdown") != "VERIFIED_EXIT"
                or self.owner.verify_durable_stop_receipt(
                    "SHUTDOWN_FLATTEN", receipt
                ) is not True
                or self.runtime.state != "STOPPED"
                or late
                or after + CLOCK_MARGIN_SECONDS
                >= next_hour - GUARD_BEFORE_FUNDING_SECONDS
            ):
                raise ValueError("HL_PRE_FUNDING_DURABLE_FLAT_BEFORE_CUTOFF_REFUSED")
        except BaseException:
            self.runtime.entry_closed.set()
            self.runtime.uncertain = True
            self.runtime.state = "STOP_INCOMPLETE"
            raise
        return {
            "schema": SCHEMA,
            "status": "ORIGINAL_NATIVE_DURABLE_STOP_FLAT_BEFORE_FUNDING",
            "next_funding_hour_utc": next_hour,
            "stop_verified_at_utc": after,
            "original_native_stop_receipt": receipt,
            "original_native_durable_stop_verified": True,
            "funding_cost_assumed_zero": False,
            "provider_actual_funding_settlement_verified": False,
            "automatic_restart_authorized": False,
            "live_trading_authorized": False,
        }
