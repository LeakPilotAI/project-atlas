"""R17+ operational PAPER-only lease source tests (no native/finance Start).

Synthetic fixtures explicitly replace exact native authority classes only
inside pytest. They do not establish real selected-release or provider rights.
"""
from __future__ import annotations

from threading import Event
from types import SimpleNamespace

import pytest

from scripts.observation_runtime import (
    personal_selected_paper_operation_issuer as issuer,
)

DIGEST = "a" * 64
INSTRUMENT = {
    "symbol": "MSFT",
    "instrument_id": "MSFT:USD:STOCK",
    "asset_class": "STOCK",
    "currency": "USD",
}
QUOTE = {
    "schema": "QD_AUTO_L1_V1",
    "symbol": "MSFT",
    "instrument_id": INSTRUMENT["instrument_id"],
    "market_status": "TRADING",
    "delay_status": "REALTIME",
    "connection_status": "CONNECTED",
}
HL_CUT = {
    "schema": "HL_CURRENT_PACKET_V1",
    "source_revision": 123,
    "execution_domain": "OPERATIONAL",
}


def synthetic_port_factory(monkeypatch):
    # This is NOT a real native issuer or real live market data; each nominal
    # production class is deliberately test-replaced for just these fixtures.
    class Owner:
        _phase = "INITIAL_READBACK_ONLY"
        release_digest = DIGEST
        def require_exact_roster(self, *, qd, perp):
            if getattr(self, "revoke", False):
                raise ValueError("ORIGINAL_JOB_REVOKED")
            return True

    class Clock:
        def require_operational(self, runtime_id):
            if getattr(self, "revoke", False):
                raise ValueError("CLOCK_REVOKED")
            return self

    class Operator:
        def activation(self, action):
            if getattr(self, "revoke", False):
                raise ValueError("OPERATOR_REVOKED")
            assert action == "AUTO_PAPER"
            return {"action": action}

    class Stop:
        def verify_session(self):
            return not getattr(self, "revoke", False)

    class IEX:
        def quote(self, instrument):
            if getattr(self, "revoke", False):
                raise ValueError("QD_EXECUTION_SOURCE_REVOKED")
            assert instrument == INSTRUMENT
            return dict(QUOTE)

    class HL:
        def _verify(self):
            if getattr(self, "revoke", False):
                raise ValueError("HL_SOURCE_REVOKED")
        def read_cut(self):
            self._verify()
            return dict(HL_CUT)

    monkeypatch.setattr(issuer, "RetainedSelectedNativeOwnerPreflight", Owner)
    monkeypatch.setattr(issuer, "NativeVersionSafePaperOperatorClock", Clock)
    monkeypatch.setattr(issuer, "NativePersonalOperatorAuthority", Operator)
    monkeypatch.setattr(issuer, "PersonalInstalledPaperStopOwner", Stop)
    monkeypatch.setattr(issuer, "IEXPaperQuotes", IEX)
    monkeypatch.setattr(issuer, "HyperliquidCurrentProducer", HL)
    monkeypatch.setattr(issuer, "require_version_safe_release_digest",
                        lambda *, clock, runtime_id, release_digest:
                        clock.require_operational(runtime_id) and True)
    qd = {"release_digest": DIGEST, "account_id": "QD"}
    perp = {"release_digest": DIGEST, "account_id": "HL"}
    owned = Owner()
    clock = Clock()
    operator = Operator()
    operator.enrollment, operator.clock, operator.runtime_id = qd, clock, "TEST-R17"
    operator.accounts = {"QUALITY_DIPS": issuer.digest(qd),
                         "HYPERLIQUID": issuer.digest(perp)}
    stop = Stop()
    stop.session_id = "test-r17-paper-session"
    stop._used = False
    installation = object()
    stop._installation = installation
    stop._runtime = SimpleNamespace(
        clock=clock, installation=installation,
        grant={"session_id": stop.session_id, "test_only": False},
        entry_closed=Event(), uncertain=False, state="RUNNING",
    )
    qd_source = IEX()
    qd_source.authority = object()
    qd_source.session_id = stop.session_id
    hl_source = HL()
    hl_source.clock, hl_source.enrollment = clock, perp
    hl_source.execution_domain = "OPERATIONAL"
    params = {
        "owner": owned, "operator": operator, "clock": clock, "stop_owner": stop,
        "qd_source": qd_source, "hl_source": hl_source, "qd": qd, "perp": perp,
    }
    return params


def test_pure_synthetic_fully_bound_paper_operation_lease_is_temporary(monkeypatch):
    params = synthetic_port_factory(monkeypatch)
    obj = issuer.NativeSelectedPaperOperationIssuer(**params)
    assert not hasattr(obj, "start")
    assert not hasattr(obj, "place_order")
    assert not hasattr(obj, "commission_accounts")
    with obj.lease(qd_instrument=INSTRUMENT) as cap:
        assert cap.check()
        receipt = cap.receipt
        assert receipt["schema"] == issuer.SCHEMA
        assert receipt["paper_only"] is True
        assert receipt["external_broker_orders_authorized"] is False
        assert receipt["live_trading_authorized"] is False
        assert receipt["account_inception_authorized"] is False
    assert cap.check() is False


@pytest.mark.parametrize("missing", [
    "owner", "operator", "clock", "stop_owner", "qd_source", "hl_source",
])
def test_synthetic_refuses_missing_original_native_dependency(monkeypatch, missing):
    params = synthetic_port_factory(monkeypatch)
    params[missing] = object()
    with pytest.raises(ValueError, match="EXACT_NATIVE_JOB_OPERATOR"):
        issuer.NativeSelectedPaperOperationIssuer(**params)


@pytest.mark.parametrize("change", [
    "preinception", "wrong_qd_release", "wrong_hl_release", "wrong_runtime_clock",
    "wrong_operator_clock", "foreign_stop_installation", "foreign_stop_session",
    "unknown_iex_authority", "foreign_hl_execution_domain", "foreign_operator_account",
])
def test_synthetic_wrong_financial_binding_refused_before_lease(monkeypatch, change):
    params = synthetic_port_factory(monkeypatch)
    if change == "preinception":
        params["owner"]._phase = "PREINCEPTION"
    elif change == "wrong_qd_release":
        params["qd"]["release_digest"] = "e" * 64
    elif change == "wrong_hl_release":
        params["perp"]["release_digest"] = "e" * 64
    elif change == "wrong_runtime_clock":
        params["stop_owner"]._runtime.clock = object()
    elif change == "wrong_operator_clock":
        params["operator"].clock = object()
    elif change == "foreign_stop_installation":
        params["stop_owner"]._runtime.installation = object()
    elif change == "foreign_stop_session":
        params["qd_source"].session_id = "OTHER_SESSION"
    elif change == "unknown_iex_authority":
        params["qd_source"].authority = None
    elif change == "foreign_hl_execution_domain":
        params["hl_source"].execution_domain = "DISPOSABLE"
    elif change == "foreign_operator_account":
        params["operator"].accounts["HYPERLIQUID"] = "f" * 64
    with pytest.raises(ValueError, match="ONE_NATIVE_RELEASE_TWO_ACCOUNTS_STOP_SCOPE"):
        issuer.NativeSelectedPaperOperationIssuer(**params)


@pytest.mark.parametrize("change", [
    "original_job_exit", "clock_revoke", "operator_revoke", "stop_revoke",
    "qd_quote_revoke", "hl_source_revoke", "stop_dispatched",
    "entry_latched", "runtime_uncertain", "runtime_stopped",
    "session_drift", "simulated_test_only_grant",
])
def test_any_revocation_prevents_operation_without_dispatch(monkeypatch, change):
    params = synthetic_port_factory(monkeypatch)
    obj = issuer.NativeSelectedPaperOperationIssuer(**params)
    if change == "original_job_exit":
        params["owner"].revoke = True
    elif change == "clock_revoke":
        params["clock"].revoke = True
    elif change == "operator_revoke":
        params["operator"].revoke = True
    elif change == "stop_revoke":
        params["stop_owner"].revoke = True
    elif change == "qd_quote_revoke":
        params["qd_source"].revoke = True
    elif change == "hl_source_revoke":
        params["hl_source"].revoke = True
    elif change == "stop_dispatched":
        params["stop_owner"]._used = True
    elif change == "entry_latched":
        params["stop_owner"]._runtime.entry_closed.set()
    elif change == "runtime_uncertain":
        params["stop_owner"]._runtime.uncertain = True
    elif change == "runtime_stopped":
        params["stop_owner"]._runtime.state = "STOPPED"
    elif change == "session_drift":
        params["stop_owner"].session_id = "NEW_SESSION"
    elif change == "simulated_test_only_grant":
        params["stop_owner"]._runtime.grant["test_only"] = True
    with pytest.raises(ValueError), obj.lease(qd_instrument=INSTRUMENT):
        pytest.fail("REVOKED_OPERATION_ENTERED")


@pytest.mark.parametrize("bad", [
    {}, {"symbol": "MSFT"}, {**INSTRUMENT, "currency": "USDC"},
    {**INSTRUMENT, "asset_class": "CRYPTO"},
])
def test_nonstock_or_partial_iex_execution_instrument_refused(monkeypatch, bad):
    params = synthetic_port_factory(monkeypatch)
    obj = issuer.NativeSelectedPaperOperationIssuer(**params)
    with pytest.raises((ValueError, AssertionError)), obj.lease(qd_instrument=bad):
        pytest.fail("INVALID_MARKET_SYMBOL_OR_INSTRUMENT_ENTERED")


def test_stop_during_lease_revokes_before_context_can_commit(monkeypatch):
    params = synthetic_port_factory(monkeypatch)
    obj = issuer.NativeSelectedPaperOperationIssuer(**params)
    with (pytest.raises(ValueError, match="LEASE_CHANGED_AFTER_USE"),
          obj.lease(qd_instrument=INSTRUMENT) as cap):
        assert cap.check()
        params["stop_owner"]._runtime.entry_closed.set()
        assert cap.check() is False
    assert cap.check() is False


def test_financial_lease_expires_after_five_seconds(monkeypatch):
    params = synthetic_port_factory(monkeypatch)
    obj = issuer.NativeSelectedPaperOperationIssuer(**params)
    mono = SimpleNamespace(current=100.0)
    monkeypatch.setattr(issuer, "time", SimpleNamespace(
        monotonic=lambda: mono.current,
    ))
    with (pytest.raises(ValueError, match="LEASE_CHANGED_AFTER_USE"),
          obj.lease(qd_instrument=INSTRUMENT) as cap):
        assert cap.check() is True
        mono.current = 105.1
        assert cap.check() is False
    assert cap.check() is False


def test_real_unselected_workstation_cannot_claim_financial_operation_issuer():
    # No patch: host workspace has neither selected R17 original PROCESS
    # custody nor an installed genuine PersonalInstalledPaperStopOwner.
    with pytest.raises(ValueError, match="EXACT_NATIVE_JOB_OPERATOR"):
        issuer.NativeSelectedPaperOperationIssuer(
            owner=object(), operator=object(), clock=object(), stop_owner=object(),
            qd_source=object(), hl_source=object(), qd={}, perp={},
        )


def test_financial_operation_lease_is_not_reentrant(monkeypatch):
    params = synthetic_port_factory(monkeypatch)
    obj = issuer.NativeSelectedPaperOperationIssuer(**params)
    with obj.lease(qd_instrument=INSTRUMENT) as cap:
        assert cap.check()
        with (pytest.raises(ValueError, match="OPERATION_ALREADY_ACTIVE"),
              obj.lease(qd_instrument=INSTRUMENT)):
            pytest.fail("CONCURRENT_OPERATION_MUST_NOT_ENTER")
        assert cap.check()
    with obj.lease(qd_instrument=INSTRUMENT) as after:
        assert after.check()


def test_revoked_or_completed_financial_lease_receipt_cannot_be_replayed(monkeypatch):
    params = synthetic_port_factory(monkeypatch)
    obj = issuer.NativeSelectedPaperOperationIssuer(**params)
    with obj.lease(qd_instrument=INSTRUMENT) as cap:
        assert cap.receipt["financial_startup_authorized"] is False
        assert cap.receipt["operating_gate_independently_accepted"] is False
    with pytest.raises(ValueError, match="REVOKED_LEASE_RECEIPT_REFUSED"):
        _ = cap.receipt


def test_source_only_prepared_stop_first_requires_real_current_both_sources(monkeypatch):
    params = synthetic_port_factory(monkeypatch)
    runtime = params["stop_owner"]._runtime
    runtime._stop_first_state = "ARMED"
    runtime._stop_first_issuer = None
    runtime.entry_closed.set()
    runtime.state = "PAUSED"
    owner = issuer.NativeSelectedPaperOperationIssuer(**params)
    at = owner.verify_prepared_for_start(qd_instrument=INSTRUMENT)
    assert type(at) is float
    assert runtime.entry_closed.is_set()
    assert runtime.state == "PAUSED"
    with (pytest.raises(ValueError, match="FINANCIAL_OPERATION_LEASE_REVOKED"),
          owner.lease(qd_instrument=INSTRUMENT)):
        pytest.fail("ARMED_PAPER_FINANCIAL_ENTRY_FORBIDDEN")
    runtime._stop_first_state = "RELEASED"
    runtime.state = "RUNNING"
    runtime.entry_closed.clear()
    with owner.lease(qd_instrument=INSTRUMENT) as cap:
        assert cap.check()


@pytest.mark.parametrize("damage", [
    "missing_latch", "wrong_phase", "stopped", "stop_used", "issuer_already_selected",
    "bad_current_iex", "bad_current_hl", "job_exited",
])
def test_prepared_source_verifier_never_releases_unverified_entry(monkeypatch, damage):
    params = synthetic_port_factory(monkeypatch)
    runtime = params["stop_owner"]._runtime
    runtime._stop_first_state = "ARMED"
    runtime._stop_first_issuer = None
    runtime.entry_closed.set()
    runtime.state = "PAUSED"
    owner = issuer.NativeSelectedPaperOperationIssuer(**params)
    if damage == "missing_latch":
        runtime.entry_closed.clear()
    elif damage == "wrong_phase":
        runtime._stop_first_state = "RELEASED"
    elif damage == "stopped":
        runtime.state = "STOP_INCOMPLETE"
    elif damage == "stop_used":
        params["stop_owner"]._used = True
    elif damage == "issuer_already_selected":
        runtime._stop_first_issuer = object()
    elif damage == "bad_current_iex":
        params["qd_source"].revoke = True
    elif damage == "bad_current_hl":
        params["hl_source"].revoke = True
    elif damage == "job_exited":
        params["owner"].revoke = True
    with pytest.raises(ValueError):
        owner.verify_prepared_for_start(qd_instrument=INSTRUMENT)
    assert runtime.state != "RUNNING"


@pytest.mark.parametrize("inactive_qd_failure", ["disconnected", "stale_quote"])
def test_hyperliquid_24x7_lease_never_requires_an_iex_quote(monkeypatch, inactive_qd_failure):
    ports = synthetic_port_factory(monkeypatch)
    if inactive_qd_failure == "disconnected":
        ports["qd_source"].revoke = True
    else:
        def stale_market(*_):
            raise ValueError("STOCK_MARKET_CLOSED_NO_CURRENT_IEX")
        ports["qd_source"].quote = stale_market
    obj = issuer.NativeSelectedPaperOperationIssuer(**ports)
    with obj.lease(lane="HYPERLIQUID", qd_instrument=None) as cap:
        assert cap.check() is True
        assert cap.receipt["source_lane"] == "HYPERLIQUID"
        assert cap.receipt["qd_instrument_id"] is None
        assert cap.receipt["paper_only"] is True
        assert not cap.receipt["external_broker_orders_authorized"]
    with (pytest.raises(issuer.PaperSourceUnavailable, match="QD_CURRENT"),
          obj.lease(lane="QUALITY_DIPS", qd_instrument=INSTRUMENT)):
        pytest.fail("CLOSED_IEX_STOCK_TRADE_CANNOT_ENTER")
    # The closed equities feed must not poison the open 24/7 perp lane.
    with obj.lease(lane="HYPERLIQUID") as later:
        assert later.check()


def test_quality_dips_live_iex_does_not_require_a_24x7_perp_cut(monkeypatch):
    ports = synthetic_port_factory(monkeypatch)
    ports["hl_source"].revoke = True
    obj = issuer.NativeSelectedPaperOperationIssuer(**ports)
    with obj.lease(lane="QUALITY_DIPS", qd_instrument=INSTRUMENT) as cap:
        assert cap.check()
        assert cap.receipt["source_lane"] == "QUALITY_DIPS"
        assert cap.receipt["qd_instrument_id"] == INSTRUMENT["instrument_id"]
    with (pytest.raises(issuer.PaperSourceUnavailable, match="HL_CURRENT"),
          obj.lease(lane="HYPERLIQUID")):
        pytest.fail("INVALID_PERP_MARKET_SOURCE_CANNOT_ENTER")


@pytest.mark.parametrize("bad_lane", ["", "QUOTES", "KALSHI", "QUALITY_DIPS_HL", 1, None])
def test_untrusted_or_unknown_lane_never_receives_paper_operation(monkeypatch, bad_lane):
    ports = synthetic_port_factory(monkeypatch)
    obj = issuer.NativeSelectedPaperOperationIssuer(**ports)
    with (pytest.raises(ValueError, match="EXACT_FINANCIAL_LANE"),
          obj.lease(lane=bad_lane, qd_instrument=INSTRUMENT)):
        pytest.fail("INVALID_LANE_MUST_NOT_HAVE_ENTRY")
    assert not obj._lease_lock.locked()


def test_prearmed_hyperliquid_start_does_not_require_open_stock_market(monkeypatch):
    ports = synthetic_port_factory(monkeypatch)
    runtime = ports["stop_owner"]._runtime
    runtime._stop_first_state = "ARMED"
    runtime._stop_first_issuer = None
    runtime.entry_closed.set()
    runtime.state = "PAUSED"
    ports["qd_source"].revoke = True
    obj = issuer.NativeSelectedPaperOperationIssuer(**ports)
    stamp = obj.verify_prepared_for_start(lane="HYPERLIQUID")
    assert type(stamp) is float
    assert runtime.entry_closed.is_set()
    assert runtime.state == "PAUSED"
    with pytest.raises(issuer.PaperSourceUnavailable, match="QD_CURRENT"):
        obj.verify_prepared_for_start(
            lane="QUALITY_DIPS", qd_instrument=INSTRUMENT)


@pytest.mark.parametrize("failure", ["stop", "native_job", "operator", "clock", "session"])
def test_all_lanes_still_revoke_on_shared_native_financial_failure(monkeypatch, failure):
    ports = synthetic_port_factory(monkeypatch)
    obj = issuer.NativeSelectedPaperOperationIssuer(**ports)
    if failure == "stop":
        ports["stop_owner"].revoke = True
    elif failure == "native_job":
        ports["owner"].revoke = True
    elif failure == "operator":
        ports["operator"].revoke = True
    elif failure == "clock":
        ports["clock"].revoke = True
    else:
        ports["stop_owner"].session_id = "CHANGED_STOP_SESSION"
    for lane in ("HYPERLIQUID", "QUALITY_DIPS"):
        with (pytest.raises(ValueError),
              obj.lease(lane=lane, qd_instrument=INSTRUMENT)):
            pytest.fail("SHARED_NATIVE_FAILURE_MUST_BLOCK_BOTH_LANES")
