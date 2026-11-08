"""Personal installed Stop owner adapter: synthetic native-free contracts only."""
import copy

import pytest
from fastapi import FastAPI

from app.services.paper_stop_receipt_ledger import PaperStopReceiptLedger
from app.services.personal_installed_stop_owner import PersonalInstalledPaperStopOwner
from app.services.personal_paper_runtime import bind_personal_unified_paper_stop
from test_personal_paper_runtime import installed
from test_unified_paper_runtime import runtime as synthetic_unified


def accepted(tmp_path):
    r = synthetic_unified()
    r.grant["session_id"] = "offline-synthetic-owner"
    r.grant["test_only"] = False
    i = installed(accounts={"QUALITY_DIPS": "a" * 64, "HYPERLIQUID": "b" * 64},
                  ports={"lanes": r.lanes, "portfolio": r.portfolio, "clock": r.clock}).i
    r.installation = i
    app = FastAPI()
    bridge = bind_personal_unified_paper_stop(
        app, runtime=r, installation=i, owned_close=type("Close", (), {
            "close_verified": lambda self, roster: True,
            "verify_exit": lambda self, roster: True,
        })(), ledger_path=tmp_path / "synthetic-ledger.sqlite",
        origin="http://127.0.0.1:18811",
        token="synthetic-source-only-control-credential-1234567890",
    )
    return r, i, bridge


def stop_result():
    return {"schema": "QD_CONTROL_STOP_V1", "phase": "FINISHED", "outcome": {
        "schema": "QD_AUTO_SHUTDOWN_V1", "mode": "SHUTDOWN_FLATTEN",
        "status": "FLATTENED", "position_state": "FLAT",
        "process_shutdown": "VERIFIED_EXIT",
        "lanes": {"QUALITY_DIPS": {"state": "ACKNOWLEDGED_FLAT_AND_DRAINED"},
                  "HYPERLIQUID": {"state": "ACKNOWLEDGED_FLAT_AND_DRAINED"}},
    }}


def test_inert_construction_requires_real_enrolled_binder_not_self_assertion(tmp_path):
    with pytest.raises(ValueError, match="PERSONAL_INSTALLED_STOP_ACCEPTED_OWNER_REQUIRED"):
        PersonalInstalledPaperStopOwner(bridge=object(), installation=object())
    assert list(tmp_path.iterdir()) == []


def test_synthetic_accepted_binder_projects_exact_session_without_start(tmp_path):
    r, installation, bridge = accepted(tmp_path)
    port = PersonalInstalledPaperStopOwner(bridge=bridge, installation=installation)
    assert port.session_id == r.grant["session_id"]
    assert port.verify_session() is True
    assert port._used is False and bridge.progress["phase"] == "IDLE"
    assert not r.entry_closed.is_set()


@pytest.mark.parametrize("damage", ["foreign_installation", "test_grant", "missing_lane",
                                  "missing_owner", "missing_ledger", "stopped", "foreign_bridge"] )
def test_reject_nonaccepted_owner_bindings_before_financial_dispatch(tmp_path, damage):
    r, installation, bridge = accepted(tmp_path)
    if damage == "foreign_installation": r.installation = object()
    elif damage == "test_grant": r.grant["test_only"] = True
    elif damage == "missing_lane": r.lanes = {"QUALITY_DIPS": r.lanes["QUALITY_DIPS"]}
    elif damage == "missing_owner": bridge.owned_close = None
    elif damage == "missing_ledger": bridge.stop_ledger = None
    elif damage == "stopped": r.state = "STOPPED"
    else: bridge.runtime = object()
    with pytest.raises(ValueError, match="PERSONAL_INSTALLED_STOP_ACCEPTED_OWNER_REQUIRED"):
        PersonalInstalledPaperStopOwner(bridge=bridge, installation=installation)
    assert bridge.progress["phase"] == "IDLE"


def test_prior_pending_intent_blocks_new_stop_owner_without_replay(tmp_path):
    r, installation, bridge = accepted(tmp_path)
    bridge.stop_ledger.reserve_fresh(r.grant["session_id"], "SHUTDOWN_FLATTEN")
    with pytest.raises(ValueError, match="PRIOR_INTENT_RECONCILIATION_REQUIRED"):
        PersonalInstalledPaperStopOwner(bridge=bridge, installation=installation)
    assert r.entry_closed.is_set()


def test_exact_owner_binding_is_rechecked_before_each_new_stop(tmp_path):
    r, installation, bridge = accepted(tmp_path)
    p = PersonalInstalledPaperStopOwner(bridge=bridge, installation=installation)
    r.grant["session_id"] = "foreign-session"
    assert p.verify_session() is False
    with pytest.raises(ValueError, match="PERSONAL_INSTALLED_STOP_OWNER_UNVERIFIED"):
        p.request_stop("SHUTDOWN_FLATTEN")
    assert p._used is False and bridge.progress["phase"] == "IDLE"


def test_one_exact_stop_dispatch_and_no_replay_with_durable_receipt(tmp_path):
    r, installation, bridge = accepted(tmp_path)
    p = PersonalInstalledPaperStopOwner(bridge=bridge, installation=installation)
    result = stop_result()
    calls = []
    bridge.request_stop = lambda mode: (calls.append(mode) or copy.deepcopy(result))
    assert p.request_stop("SHUTDOWN_FLATTEN") == result
    assert calls == ["SHUTDOWN_FLATTEN"]
    with pytest.raises(ValueError, match="ONCE_ONLY"):
        p.request_stop("SHUTDOWN_FLATTEN")
    assert not p.verify_durable_stop_receipt("SHUTDOWN_FLATTEN", result)
    bridge.progress = copy.deepcopy(result)
    bridge._receipt_persisted = True
    bridge.stop_ledger.reserve_fresh(p.session_id, "SHUTDOWN_FLATTEN")
    bridge.stop_ledger.finish(p.session_id, "SHUTDOWN_FLATTEN", result)
    assert p.verify_durable_stop_receipt("SHUTDOWN_FLATTEN", result) is True
    assert p.verify_durable_stop_receipt("EMERGENCY", result) is False
    forged = copy.deepcopy(result)
    forged["outcome"]["lanes"]["HYPERLIQUID"]["state"] = "OPEN"
    assert p.verify_durable_stop_receipt("SHUTDOWN_FLATTEN", forged) is False


def test_unknown_dispatch_never_retries_financial_owner(tmp_path):
    r, installation, bridge = accepted(tmp_path)
    p = PersonalInstalledPaperStopOwner(bridge=bridge, installation=installation)
    called = []
    def unknown(mode):
        called.append(mode)
        raise OSError("synthetic lost reply")
    bridge.request_stop = unknown
    with pytest.raises(OSError, match="synthetic lost reply"):
        p.request_stop("SHUTDOWN_FLATTEN")
    with pytest.raises(ValueError, match="ONCE_ONLY"):
        p.request_stop("SHUTDOWN_FLATTEN")
    assert len(called) == 1 and p.verify_durable_stop_receipt("SHUTDOWN_FLATTEN", stop_result()) is False


def test_one_step_installed_owner_opt_in_composition(tmp_path):
    from app.services.personal_installed_stop_owner import bind_personal_installed_gui_stop_owner
    r = synthetic_unified()
    r.grant["session_id"] = "offline-composed-owner"
    r.grant["test_only"] = False
    i = installed(accounts={"QUALITY_DIPS": "a" * 64, "HYPERLIQUID": "b" * 64},
                  ports={"lanes": r.lanes, "portfolio": r.portfolio, "clock": r.clock}).i
    r.installation = i
    app = FastAPI()
    port = bind_personal_installed_gui_stop_owner(
        app, runtime=r, installation=i, owned_close=type("Owned", (), {
            "close_verified": lambda self, roster: True,
            "verify_exit": lambda self, roster: True,
        })(), ledger_path=tmp_path / "offline-composition.sqlite",
        origin="http://127.0.0.1:18811", token="synthetic-source-only-control-credential-1234567890")
    assert type(port) is PersonalInstalledPaperStopOwner
    assert port.session_id == "offline-composed-owner"
    assert port.verify_session()
    assert any(route.path == "/_atlas/control/stop-session" for route in app.routes)
    assert port._used is False and not r.entry_closed.is_set()


def test_one_step_composition_refuses_unaccepted_runtime_without_ledger(tmp_path):
    from app.services.personal_installed_stop_owner import bind_personal_installed_gui_stop_owner
    app = FastAPI()
    with pytest.raises(ValueError, match="PERSONAL_ACCEPTED_SESSION_REQUIRED"):
        bind_personal_installed_gui_stop_owner(
            app, runtime=object(), installation=object(), owned_close=None,
            ledger_path=tmp_path / "not-created.sqlite",
            origin="http://127.0.0.1:18811", token="synthetic-source-only-control-credential-1234567890")
    assert not (tmp_path / "not-created.sqlite").exists()
    assert not any(route.path == "/_atlas/control/stop-session" for route in app.routes)
