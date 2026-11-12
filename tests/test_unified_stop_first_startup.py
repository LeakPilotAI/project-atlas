"""Stop-first native PAPER startup ordering: source-only/disposable contracts.

No actual installed financial issuer, accounts, markets, network or native
process is created by these synthetic fixtures. Real release acceptance
requires selected original Windows handles and operator/ledger proofs.
"""
from __future__ import annotations

from contextlib import contextmanager

import pytest
from app.services.unified_paper_runtime import UnifiedPaperRuntime
from test_unified_paper_runtime import NOW, Custody, Installation, Lane


def made(monkeypatch):
    import app.services.personal_installed_stop_owner as stop_mod
    import app.services.personal_paper_runtime as personal_mod

    import scripts.observation_runtime.personal_selected_paper_operation_issuer as issuer_mod

    # Injected exact types ONLY inside the synthetic test. The unpatched
    # production code requires actual PersonalOperatorInstallation,
    # PersonalInstalledPaperStopOwner and NativeSelectedPaperOperationIssuer.
    monkeypatch.setattr(personal_mod, "PersonalOperatorInstallation", Installation)
    ports = {
        "QUALITY_DIPS": Lane("QUALITY_DIPS", closed=True),
        "HYPERLIQUID": Lane("HYPERLIQUID"),
    }
    inst = Installation()
    inst.accounts = {"QUALITY_DIPS": "a"*64, "HYPERLIQUID": "b"*64}
    runtime = UnifiedPaperRuntime(
        lanes=ports, installation=inst, portfolio=Custody(), clock=lambda: NOW,
    )
    grant = {"session_id": "DISPOSABLE_TWO_PHASE_ONLY", "test_only": False}

    class Stop:
        _used = False
        def __init__(self, runtime):
            self._runtime = runtime
            self.session_id = runtime.grant["session_id"]
        def verify_session(self):
            return self._runtime.grant["session_id"] == self.session_id

    class Issuer:
        _revoke = False
        def __init__(self, stop_owner):
            self.stop_owner = stop_owner
            self._session = stop_owner.session_id
            self.calls = 0
            self.unavailable = set()
        def verify_prepared_for_start(self, *, qd_instrument, lane="BOTH"):
            import time
            self.calls += 1
            if lane not in ("BOTH", "QUALITY_DIPS", "HYPERLIQUID"):
                raise ValueError("FOREIGN_SOURCE_LANE")
            if qd_instrument != {"symbol": "MSFT"} and lane != "HYPERLIQUID":
                raise ValueError("STALE_OR_FOREIGN_SOURCE")
            if not self.stop_owner.verify_session():
                raise ValueError("STOP_SESSION_UNVERIFIED")
            return time.monotonic()
        @contextmanager
        def lease(self, *, qd_instrument, lane="BOTH"):
            if self._revoke:
                raise ValueError("SIMULATED_ISSUER_REVOKED")
            if lane in self.unavailable:
                raise issuer_mod.PaperSourceUnavailable(
                    "SYNTHETIC_READ_ONLY_" + lane + "_FEED_UNAVAILABLE")
            self.calls += 1
            assert lane in ("BOTH", "QUALITY_DIPS", "HYPERLIQUID")
            assert qd_instrument == {"symbol": "MSFT"} or lane == "HYPERLIQUID"
            class Lease:
                def check(self):
                    return True
            yield Lease()

    monkeypatch.setattr(stop_mod, "PersonalInstalledPaperStopOwner", Stop)
    monkeypatch.setattr(issuer_mod, "NativeSelectedPaperOperationIssuer", Issuer)
    return runtime, grant, Stop, Issuer


def test_genuine_unpatched_noninstalled_runtime_refuses_arm():
    r = UnifiedPaperRuntime(
        lanes={"QUALITY_DIPS": Lane("QUALITY_DIPS"),
               "HYPERLIQUID": Lane("HYPERLIQUID")},
        installation=Installation(), portfolio=Custody(), clock=lambda: NOW,
    )
    with pytest.raises(ValueError, match="STOP_FIRST_REAL_INSTALLED_SESSION"):
        r.arm_stop_first({"session_id": "NO_NATIVE_OPERATOR", "test_only": False})
    assert r.grant is None
    assert r.state == "STOPPED"


def test_stop_first_synthetic_arms_with_latch_before_stop_is_bound(monkeypatch):
    r, grant, _Stop, _Issuer = made(monkeypatch)
    result = r.arm_stop_first(grant)
    assert result["state"] == "PAUSED"
    assert result["entry_closed"] is True
    assert result["paper_entry_authorized"] is False
    assert r.state == "PAUSED" and r.entry_closed.is_set()
    assert r._stop_first_state == "ARMED" and r._stop_first_issuer is None
    assert not any(v.calls for v in r.lanes.values())
    with pytest.raises(ValueError, match="STOP_FIRST_NEW_SESSION"):
        r.arm_stop_first(grant)
    for kind in ("ENTRY", "MARK", "FUNDING", "EXIT"):
        with pytest.raises(ValueError, match="STOP_FIRST_ALL_FINANCIAL_ADMISSIONS"):
            r.dispatch("HYPERLIQUID", {"operation_id":kind,"kind":kind})
    with pytest.raises(ValueError, match="STOP_FIRST_ALL_FINANCIAL_ADMISSIONS"):
        r.admit_resting({"kind":"RESTING_ORDER"})


@pytest.mark.parametrize("grant", [
    {"test_only": True, "session_id": "TEST"},
    {"test_only": False},
    {"session_id": "", "test_only": False},
    {"session_id": "x"*129, "test_only": False},
    {},
    None,
])
def test_synthetic_arm_requires_non_test_exact_session(monkeypatch, grant):
    r, _, _, _ = made(monkeypatch)
    with pytest.raises(ValueError, match="STOP_FIRST_REAL_INSTALLED_SESSION"):
        r.arm_stop_first(grant)
    assert r.state == "STOPPED"
    assert not r.entry_closed.is_set()


def test_synthetic_explicitly_blocks_old_direct_start_for_real_personal_install(monkeypatch):
    r, grant, _, _ = made(monkeypatch)
    with pytest.raises(ValueError, match="STOP_FIRST_START_MANDATORY"):
        r.start(grant)
    assert r.grant is None
    assert r.state == "STOPPED"


def test_synthetic_restart_unknown_refuses_retry_and_latches_entry(monkeypatch):
    r, grant, _, _ = made(monkeypatch)
    r.portfolio.verify_restart = lambda g: False
    with pytest.raises(ValueError, match="STOP_FIRST_UNRESOLVED_RESTART"):
        r.arm_stop_first(grant)
    assert r.state == "STOP_INCOMPLETE"
    assert r.uncertain
    assert r.entry_closed.is_set()
    assert r._stop_first_state == "REFUSED"
    with pytest.raises(ValueError, match="STOP_FIRST_NEW_SESSION"):
        r.arm_stop_first(grant)


def test_synthetic_cannot_resume_without_exact_native_issuer(monkeypatch):
    r, grant, Stop, _Issuer = made(monkeypatch)
    r.arm_stop_first(grant)
    stop = Stop(r)
    with pytest.raises(ValueError, match="EXACT_INSTALLED_STOP_AND_ISSUER"):
        r.resume_stop_first(stop_owner=stop, issuer=object(),
                            qd_instrument={"symbol":"MSFT"})
    assert r.state == "PAUSED" and r.entry_closed.is_set()


def test_synthetic_stop_first_transition_requires_stop_then_issuer(monkeypatch):
    r, grant, Stop, Issuer = made(monkeypatch)
    r.arm_stop_first(grant)
    stop = Stop(r)
    source = Issuer(stop)
    response = r.resume_stop_first(
        stop_owner=stop, issuer=source, qd_instrument={"symbol":"MSFT"},
    )
    assert response["state"] == "RUNNING"
    assert response["external_live_orders_authorized"] is False
    assert r.state == "RUNNING" and not r.entry_closed.is_set()
    assert r._stop_first_state == "RELEASED"
    assert r._stop_first_issuer is source
    assert r._stop_first_instrument == {"symbol":"MSFT"}
    assert source.calls == 1
    with pytest.raises(ValueError, match="UNRELEASED_OR_EXPIRED"):
        r.resume_stop_first(
            stop_owner=stop, issuer=source, qd_instrument={"symbol":"MSFT"},
        )
    assert not any(v.calls for v in r.lanes.values())


def test_synthetic_stale_market_refuses_release_while_entry_stays_closed(monkeypatch):
    r, grant, Stop, Issuer = made(monkeypatch)
    r.arm_stop_first(grant)
    stop = Stop(r)
    with pytest.raises(ValueError, match="STALE_OR_FOREIGN_SOURCE"):
        r.resume_stop_first(
            stop_owner=stop, issuer=Issuer(stop),
            qd_instrument={"symbol":"NOT_CURRENT"},
        )
    assert r.state == "PAUSED" and r.entry_closed.is_set()


def test_synthetic_stop_already_dispatched_prevents_resume(monkeypatch):
    r, grant, Stop, Issuer = made(monkeypatch)
    r.arm_stop_first(grant)
    stop = Stop(r)
    stop._used = True
    with pytest.raises(ValueError, match="UNRELEASED_OR_EXPIRED"):
        r.resume_stop_first(
            stop_owner=stop, issuer=Issuer(stop),
            qd_instrument={"symbol":"MSFT"},
        )
    assert r.entry_closed.is_set()


def test_synthetic_released_entry_is_always_source_issuer_guarded(monkeypatch):
    r, grant, Stop, Issuer = made(monkeypatch)
    r.arm_stop_first(grant)
    stop = Stop(r)
    source = Issuer(stop)
    r.resume_stop_first(
        stop_owner=stop, issuer=source, qd_instrument={"symbol":"MSFT"},
    )
    r._stop_first_issuer = None
    with pytest.raises(ValueError, match="OPERATION_ISSUER_MISSING"):
        r.dispatch("HYPERLIQUID", {"operation_id":"ONE","kind":"ENTRY"})
    assert not any(v.calls for v in r.lanes.values())


def test_synthetic_runtime_does_not_allow_forged_test_grant_after_arm(monkeypatch):
    r, grant, Stop, Issuer = made(monkeypatch)
    r.arm_stop_first(grant)
    stop = Stop(r)
    source = Issuer(stop)
    r.grant["test_only"] = True
    with pytest.raises(ValueError, match="UNRELEASED_OR_EXPIRED"):
        r.resume_stop_first(
            stop_owner=stop, issuer=source,
            qd_instrument={"symbol":"MSFT"},
        )
    assert r.entry_closed.is_set()


def test_source_lease_denies_run_when_revoked_after_resume(monkeypatch):
    r, grant, Stop, Issuer = made(monkeypatch)
    r.arm_stop_first(grant)
    stop = Stop(r)
    source = Issuer(stop)
    r.resume_stop_first(
        stop_owner=stop, issuer=source, qd_instrument={"symbol":"MSFT"},
    )
    source._revoke = True
    with pytest.raises(ValueError, match="SIMULATED_ISSUER_REVOKED"):
        r.dispatch("HYPERLIQUID", {"operation_id":"ONE","kind":"ENTRY"})
    assert not any(v.calls for v in r.lanes.values())


def test_stop_request_latch_wins_over_prepared_resume(monkeypatch):
    r, grant, Stop, Issuer = made(monkeypatch)
    r.arm_stop_first(grant)
    stop = Stop(r)
    r._stop_requested.set()
    with pytest.raises(ValueError, match="UNRELEASED_OR_EXPIRED"):
        r.resume_stop_first(stop_owner=stop, issuer=Issuer(stop),
                            qd_instrument={"symbol":"MSFT"})
    assert r.state == "PAUSED" and r.entry_closed.is_set()


def test_failed_operational_source_admission_latches_uncertain(monkeypatch):
    r, grant, Stop, Issuer = made(monkeypatch)
    r.arm_stop_first(grant)
    stop = Stop(r)
    source = Issuer(stop)
    r.resume_stop_first(stop_owner=stop, issuer=source,
                        qd_instrument={"symbol":"MSFT"})
    source._revoke = True
    with pytest.raises(ValueError, match="SIMULATED_ISSUER_REVOKED"):
        r.admit_resting({"kind":"RESTING_ORDER"})
    assert r.uncertain and r.entry_closed.is_set()
    assert not any(v.calls for v in r.lanes.values())


def test_real_personal_stop_binder_accepts_prepared_paused_session(tmp_path):
    """Real Stop binder/SQLite ledger, synthetic account/custody data only."""
    from app.services.personal_installed_stop_owner import (
        PersonalInstalledPaperStopOwner,
    )
    from app.services.personal_paper_runtime import bind_personal_unified_paper_stop
    from fastapi import FastAPI
    from test_personal_paper_runtime import installed

    ports = {"QUALITY_DIPS": Lane("QUALITY_DIPS", closed=True),
             "HYPERLIQUID": Lane("HYPERLIQUID")}
    portfolio = Custody()
    clock = lambda: NOW
    i = installed(
        accounts={"QUALITY_DIPS":"a"*64, "HYPERLIQUID":"b"*64},
        ports={"lanes": ports, "portfolio": portfolio, "clock": clock},
    ).i
    r = UnifiedPaperRuntime(
        lanes=ports, installation=i, portfolio=portfolio, clock=clock,
    )
    grant = {"session_id":"SYNTHETIC_PHASED_STOP_SQLITE",
             "test_only":False}
    armed = r.arm_stop_first(grant)
    assert armed["paper_entry_authorized"] is False
    assert r.state == "PAUSED" and r.entry_closed.is_set()
    ledger = tmp_path/"durable-synthetic-stop-first.sqlite"
    bridge = bind_personal_unified_paper_stop(
        FastAPI(), runtime=r, installation=i,
        owned_close=type("Close",(),{
            "close_verified":lambda self,roster:True,
            "verify_exit":lambda self,roster:True,
        })(),
        ledger_path=ledger,
        origin="http://127.0.0.1:18811",
        token="synthetic-two-phase-no-production-credential-1234567890",
    )
    stop_owner = PersonalInstalledPaperStopOwner(bridge=bridge,installation=i)
    assert ledger.is_file()
    assert stop_owner.session_id == grant["session_id"]
    assert stop_owner.verify_session()
    assert stop_owner._used is False
    assert r.entry_closed.is_set()
    with pytest.raises(ValueError,match="STOP_FIRST_ALL_FINANCIAL_ADMISSIONS"):
        r.dispatch("HYPERLIQUID",{"operation_id":"DISPOSABLE-ONE","kind":"ENTRY"})
    # Stop is already bound; a session can still be shut down while PAUSED,
    # even if no provider/source or trading issuer has been constructed.
    receipt = stop_owner.request_stop("SHUTDOWN_FLATTEN")
    assert receipt["schema"] == "QD_CONTROL_STOP_V1"
    assert receipt["phase"] == "FINISHED"
    assert r.entry_closed.is_set()
    assert r._stop_requested.is_set()
    assert stop_owner._used is True
    assert r._stop_first_state != "RELEASED"


@pytest.mark.asyncio
async def test_synthetic_release_dispatches_only_inside_bound_issuer_lease(monkeypatch):
    r, grant, Stop, Issuer = made(monkeypatch)
    r.arm_stop_first(grant)
    stop = Stop(r)
    source = Issuer(stop)
    r.resume_stop_first(stop_owner=stop, issuer=source,
                        qd_instrument={"symbol":"MSFT"})
    await r.poll()
    assert source.calls == 1
    result = r.dispatch("HYPERLIQUID",{"operation_id":"SYNTHETIC_ENTRY","kind":"ENTRY"})
    assert result["state"] == "ACKNOWLEDGED"
    assert len(r.lanes["HYPERLIQUID"].calls) == 1
    assert source.calls >= 2
    assert not r.entry_closed.is_set()


@pytest.mark.asyncio
async def test_perp_paper_after_hours_survives_iex_feed_refusal_without_global_stop(
        monkeypatch):
    """A closed stock market must never poison an otherwise valid 24/7 lane."""
    import scripts.observation_runtime.personal_selected_paper_operation_issuer as src

    r, grant, Stop, Issuer = made(monkeypatch)
    r.arm_stop_first(grant)
    stop = Stop(r)
    source = Issuer(stop)
    r.resume_stop_first(
        stop_owner=stop, issuer=source, qd_instrument=None,
        source_lane="HYPERLIQUID",
    )
    source.unavailable.add("QUALITY_DIPS")
    assert r._stop_first_initial_source_lane == "HYPERLIQUID"
    await r.poll()
    with pytest.raises(src.PaperSourceUnavailable, match="QUALITY_DIPS"):
        r.dispatch("QUALITY_DIPS", {
            "operation_id": "CLOSED_EQUITIES_REFUSED",
            "kind": "ENTRY",
        })
    assert r.uncertain is False
    assert r.entry_closed.is_set() is False
    assert r.state == "RUNNING"
    assert not r.lanes["QUALITY_DIPS"].calls
    receipt = r.dispatch("HYPERLIQUID", {
        "operation_id": "CONTINUE_PERP_24_7",
        "kind": "ENTRY",
    })
    assert receipt["state"] == "ACKNOWLEDGED"
    assert len(r.lanes["HYPERLIQUID"].calls) == 1
    assert r.uncertain is False


@pytest.mark.asyncio
async def test_perp_feed_refusal_does_not_fake_a_perp_fill(monkeypatch):
    import scripts.observation_runtime.personal_selected_paper_operation_issuer as src

    r, grant, Stop, Issuer = made(monkeypatch)
    r.arm_stop_first(grant)
    stop = Stop(r)
    source = Issuer(stop)
    r.resume_stop_first(
        stop_owner=stop, issuer=source, qd_instrument=None,
        source_lane="HYPERLIQUID",
    )
    source.unavailable.add("HYPERLIQUID")
    await r.poll()
    with pytest.raises(src.PaperSourceUnavailable, match="HYPERLIQUID"):
        r.dispatch("HYPERLIQUID", {
            "operation_id": "INACTIVE_BOOK_NO_FILL",
            "kind": "ENTRY",
        })
    assert not r.lanes["HYPERLIQUID"].calls
    assert r.uncertain is False
    assert not r.entry_closed.is_set()
    source.unavailable.clear()
    assert r.dispatch("HYPERLIQUID", {
        "operation_id": "VALID_BOOK_FIRST_FILL",
        "kind": "ENTRY",
    })["state"] == "ACKNOWLEDGED"


def test_perp_resting_admission_uses_only_perp_source(monkeypatch):
    import scripts.observation_runtime.personal_selected_paper_operation_issuer as src

    r, grant, Stop, Issuer = made(monkeypatch)
    r.arm_stop_first(grant)
    stop = Stop(r)
    source = Issuer(stop)
    r.resume_stop_first(
        stop_owner=stop, issuer=source,
        source_lane="HYPERLIQUID", qd_instrument=None,
    )
    source.unavailable.add("HYPERLIQUID")
    with pytest.raises(src.PaperSourceUnavailable, match="HYPERLIQUID"):
        r.admit_resting({"kind": "RESTING_ORDER"})
    assert r.uncertain is False
    assert not r.entry_closed.is_set()
    assert not any(port.calls for port in r.lanes.values())
