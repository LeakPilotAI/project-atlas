"""Disposable checks of the original financial Stop-first START caller.

Every native class/port is intentionally monkeypatched: no accounts, sockets,
selected release, app routes, provider credentials, Start or Stop are touched.
"""
from __future__ import annotations

from threading import Event
from types import SimpleNamespace

import pytest

from scripts.observation_runtime import atlas_original_stop_first_start as start


def fixture_ports(monkeypatch):
    from app.services import personal_installed_stop_owner as stop_module
    from app.services import personal_paper_runtime as policy_module
    from app.services import unified_paper_runtime as runtime_module
    from scripts.observation_runtime import personal_selected_paper_operation_issuer as issuer_module

    events = []
    faults = set()

    class Installation:
        pass

    class Runtime:
        def __init__(self, installation):
            self.installation = installation
            self.state = "STOPPED"
            self.grant = None
            self.uncertain = False
            self._stop_first_state = "UNUSED"
            self.entry_closed = Event()

        def arm_stop_first(self, grant):
            events.append("arm")
            if "arm" in faults:
                raise ValueError("TEST_ARMING_REFUSED")
            self.grant = grant
            self.state = "PAUSED"
            self._stop_first_state = "ARMED"
            self.entry_closed.set()
            return {
                "state": "PAUSED", "entry_closed": True,
                "native_stop_binding_required": True,
                "paper_entry_authorized": False,
            }

        def resume_stop_first(self, *, stop_owner, issuer, qd_instrument,
                              source_lane):
            events.append("resume")
            assert type(stop_owner) is Stop
            assert type(issuer) is Issuer
            assert source_lane in ("BOTH", "HYPERLIQUID", "QUALITY_DIPS")
            if "resume" in faults:
                raise ValueError("TEST_SOURCE_OR_STOP_REFUSED")
            self.state = "RUNNING"
            self._stop_first_state = "RELEASED"
            self.entry_closed.clear()
            if "invalid_receipt" in faults:
                return {"state": "UNKNOWN"}
            return {
                "state": "RUNNING", "native_stop_bound": True,
                "external_live_orders_authorized": False,
            }

    class Stop:
        def __init__(self, runtime):
            self._runtime = runtime
            self._used = False

        def verify_session(self):
            return "verify_stop" not in faults

        def request_stop(self, mode):
            events.append("shutdown_flatten")
            assert mode == "SHUTDOWN_FLATTEN"
            assert not self._used
            self._used = True
            if "request_stop" in faults:
                raise ValueError("TEST_STOP_OUTCOME_UNKNOWN")
            self._runtime.state = "STOPPED"
            self._runtime.entry_closed.set()
            return {"schema": "QD_CONTROL_STOP_V1", "phase": "FINISHED",
                    "outcome": {"mode": mode, "status": "FLATTENED",
                                "position_state": "FLAT",
                                "process_shutdown": "VERIFIED_EXIT"}}

        def verify_durable_stop_receipt(self, mode, receipt):
            events.append("verify_durable_flat")
            return (self._used and mode == "SHUTDOWN_FLATTEN"
                    and receipt.get("schema") == "QD_CONTROL_STOP_V1"
                    and receipt.get("outcome", {}).get("status") == "FLATTENED"
                    and "durable_receipt" not in faults)

    class Issuer:
        def __init__(self, *, owner, operator, clock, stop_owner, qd_source,
                     hl_source, qd, perp):
            events.append("source_issuer")
            if "source_issuer" in faults:
                raise ValueError("TEST_SOURCE_ISSUER_REFUSED")
            self.stop_owner = stop_owner
            self.revoked = False

        def revoke(self):
            self.revoked = True
            events.append("issuer_revoke")

    def bind(app, *, runtime, installation, owned_close, ledger_path,
             origin, token, connection_factory):
        events.append("bind_stop")
        assert runtime.state == "PAUSED" and runtime.entry_closed.is_set()
        if "bind_stop" in faults:
            raise ValueError("TEST_DURABLE_STOP_BIND_REFUSED")
        return Stop(runtime)

    monkeypatch.setattr(policy_module, "PersonalOperatorInstallation", Installation)
    monkeypatch.setattr(runtime_module, "UnifiedPaperRuntime", Runtime)
    monkeypatch.setattr(stop_module, "PersonalInstalledPaperStopOwner", Stop)
    monkeypatch.setattr(
        stop_module, "bind_personal_installed_gui_stop_owner", bind,
    )
    monkeypatch.setattr(issuer_module, "NativeSelectedPaperOperationIssuer", Issuer)
    monkeypatch.setattr(start, "_require_selected_source",
                        lambda value: events.append("selected_source") or True)
    def disposable_only_hl_cost_preflight(received):
        assert received["source_lane"] in ("HYPERLIQUID", "BOTH")
        assert (received["source_lane"] != "BOTH"
                or type(received["qd_instrument"]) is dict)
        return {"financial_paper_start_authorized": False,
                "live_trading_authorized": False}
    monkeypatch.setattr(start, "require_original_hl_conservative_start_preflight",
                        disposable_only_hl_cost_preflight)
    installation = Installation()
    runtime = Runtime(installation)
    kwargs = {
        "runtime": runtime, "grant": {
            "session_id": "TEST_ORIGINAL_PAPER_SESSION",
            "test_only": False, "live_trading_authorized": False,
        },
        "installation": installation,
        "owner": SimpleNamespace(release_digest="a" * 64),
        "operator": object(), "clock": object(), "qd_source": object(),
        "hl_source": object(), "qd": {"account_id": "TEST_QD"},
        "perp": {"account_id": "TEST_HL"},
        "app": object(), "owned_close": object(),
        "ledger_path": r"D:\AtlasCustody\SIMULATION_ONLY\stop.sqlite",
        "origin": "http://127.0.0.1:7777",
        "token": "TEST_LOCAL_ONLY",
        "source_lane": "BOTH",
        "qd_instrument": {"symbol": "MSFT", "instrument_id": "TEST_QD_MSFT"},
    }
    return SimpleNamespace(
        kwargs=kwargs, runtime=runtime, events=events, faults=faults,
    )


def test_original_paper_start_always_arms_and_binds_stop_before_sources(
        monkeypatch):
    data = fixture_ports(monkeypatch)
    stop, issuer = start.start_accepted_original_paper_once(**data.kwargs)
    assert data.events == ["selected_source", "arm", "bind_stop",
                           "source_issuer", "resume"]
    assert issuer.stop_owner is stop
    assert data.runtime.state == "RUNNING"
    assert not data.runtime.entry_closed.is_set()
    assert stop.verify_session() is True
    assert not stop._used


def test_hyperliquid_lane_does_not_require_equity_open_or_iex_entry(monkeypatch):
    data = fixture_ports(monkeypatch)
    data.kwargs["source_lane"] = "HYPERLIQUID"
    data.kwargs["qd_instrument"] = None
    monkeypatch.setattr(
        start, "require_original_hl_conservative_start_preflight",
        lambda scope: data.events.append("native_hl_fee_funding_preflight"),
    )
    stop, issuer = start.start_accepted_original_paper_once(**data.kwargs)
    assert issuer.stop_owner is stop
    assert data.runtime.state == "RUNNING"
    assert data.events.index("bind_stop") < data.events.index("source_issuer")


@pytest.mark.parametrize("field,value", [
    ("grant", {"test_only": True, "session_id": "TEST"}),
    ("source_lane", "UNVERIFIED"),
    ("source_lane", None),
    ("owned_close", None),
    ("qd_instrument", None),
    ("installation", object()),
])
def test_original_start_refuses_static_bad_input_before_any_effect(
        monkeypatch, field, value):
    data = fixture_ports(monkeypatch)
    data.kwargs[field] = value
    with pytest.raises(ValueError, match="EXACT_PRECOMMISSIONED_INPUTS"):
        start.start_accepted_original_paper_once(**data.kwargs)
    assert data.events == []
    assert data.runtime.state == "STOPPED"
    assert data.runtime.grant is None


def test_original_start_refuses_workspace_or_unselected_before_arm(monkeypatch):
    data = fixture_ports(monkeypatch)
    def refused(_):
        raise ValueError("TEST_UNSELECTED_SOURCE")
    monkeypatch.setattr(start, "_require_selected_source", refused)
    with pytest.raises(ValueError, match="TEST_UNSELECTED_SOURCE"):
        start.start_accepted_original_paper_once(**data.kwargs)
    assert data.events == []
    assert data.runtime.state == "STOPPED"


@pytest.mark.parametrize("failure", [
    "bind_stop", "source_issuer", "resume", "invalid_receipt",
])
def test_original_start_failure_never_leaves_running_unstopped(monkeypatch,
                                                                  failure):
    data = fixture_ports(monkeypatch)
    data.faults.add(failure)
    with pytest.raises(ValueError):
        start.start_accepted_original_paper_once(**data.kwargs)
    assert data.runtime.entry_closed.is_set()
    assert data.events[:2] == ["selected_source", "arm"]
    assert data.events.index("bind_stop") < (
        data.events.index("source_issuer") if "source_issuer" in data.events
        else len(data.events)
    )
    if failure == "bind_stop":
        assert "shutdown_flatten" not in data.events
        assert data.runtime.uncertain is True
        assert data.runtime.state == "STOP_INCOMPLETE"
    else:
        assert data.events.count("shutdown_flatten") == 1
        assert data.events.count("verify_durable_flat") == 1
        assert data.runtime.state == "STOPPED"


@pytest.mark.parametrize("failure", ["request_stop", "durable_receipt"])
def test_original_start_stop_uncertainty_is_terminal(monkeypatch, failure):
    data = fixture_ports(monkeypatch)
    data.faults.update(("resume", failure))
    with pytest.raises(ValueError, match="STOP_RECONCILIATION_REQUIRED"):
        start.start_accepted_original_paper_once(**data.kwargs)
    assert data.runtime.entry_closed.is_set()
    assert data.runtime.state == "STOP_INCOMPLETE"
    assert data.runtime.uncertain is True
    assert data.events.count("shutdown_flatten") == 1


@pytest.mark.asyncio
async def test_original_bounded_run_exits_only_with_durable_flat_ack(monkeypatch):
    from app.services import personal_installed_stop_owner
    data = fixture_ports(monkeypatch)
    data.kwargs["source_lane"] = "QUALITY_DIPS"

    async def supervised(*, owner, seconds, interval,
                         intrahour_flat_before_funding):
        data.events.append("financial_supervision")
        assert data.runtime.state == "RUNNING"
        assert seconds == 120 and interval == 1
        assert intrahour_flat_before_funding is False
        return owner.request_stop("SHUTDOWN_FLATTEN")

    monkeypatch.setattr(
        personal_installed_stop_owner,
        "run_personal_installed_owner_session", supervised,
    )
    receipt = await start.run_accepted_original_paper_session(
        startup=data.kwargs, seconds=120,
    )
    assert receipt["outcome"]["status"] == "FLATTENED"
    assert data.runtime.state == "STOPPED"
    assert data.runtime.entry_closed.is_set()
    assert data.events.index("resume") < data.events.index("financial_supervision")
    assert data.events.index("shutdown_flatten") < data.events.index("issuer_revoke")
    assert data.events.count("verify_durable_flat") == 1


@pytest.mark.asyncio
async def test_original_supervised_run_refuses_false_flat_ack(monkeypatch):
    from app.services import personal_installed_stop_owner
    data = fixture_ports(monkeypatch)
    data.kwargs["source_lane"] = "QUALITY_DIPS"

    async def refused(*, owner, seconds, interval, intrahour_flat_before_funding):
        data.events.append("financial_supervision")
        owner.request_stop("SHUTDOWN_FLATTEN")
        return {"schema": "QD_CONTROL_STOP_V1", "phase": "FINISHED",
                "outcome": {"status": "SHUTDOWN_INCOMPLETE",
                            "position_state": "UNKNOWN",
                            "process_shutdown": "UNVERIFIED"}}

    monkeypatch.setattr(
        personal_installed_stop_owner,
        "run_personal_installed_owner_session", refused,
    )
    with pytest.raises(ValueError, match="DURABLE_FLAT_REQUIRED"):
        await start.run_accepted_original_paper_session(
            startup=data.kwargs, seconds=120,
        )
    assert data.runtime.entry_closed.is_set()
    assert data.runtime.uncertain is True
    assert data.events.count("shutdown_flatten") == 1
    assert data.events.count("issuer_revoke") == 1


@pytest.mark.asyncio
async def test_original_supervisor_crash_latches_entries_and_revokes_issuer(
        monkeypatch):
    from app.services import personal_installed_stop_owner
    data = fixture_ports(monkeypatch)
    data.kwargs["source_lane"] = "QUALITY_DIPS"

    async def crash(**_kwargs):
        raise OSError("TEST_SUPERVISION_INTERRUPTED_AFTER_START")

    monkeypatch.setattr(
        personal_installed_stop_owner,
        "run_personal_installed_owner_session", crash,
    )
    with pytest.raises(OSError, match="TEST_SUPERVISION_INTERRUPTED"):
        await start.run_accepted_original_paper_session(
            startup=data.kwargs, seconds=120,
        )
    assert data.runtime.entry_closed.is_set()
    assert data.runtime.state == "STOPPED"
    assert data.runtime.uncertain is False
    assert data.events.count("shutdown_flatten") == 1
    assert data.events.count("verify_durable_flat") == 1
    assert data.events.count("issuer_revoke") == 1


@pytest.mark.asyncio
async def test_original_invalid_run_duration_refuses_before_financial_arm(
        monkeypatch):
    data = fixture_ports(monkeypatch)
    with pytest.raises(ValueError, match="EXACT_BOUNDED_SESSION_REQUIRED"):
        await start.run_accepted_original_paper_session(
            startup=data.kwargs, seconds=0,
        )
    assert data.events == []
    assert data.runtime.state == "STOPPED"


@pytest.mark.asyncio
async def test_hl_only_paper_requires_conservative_time_guard_before_any_start(
        monkeypatch):
    data = fixture_ports(monkeypatch)
    data.kwargs["source_lane"] = "HYPERLIQUID"
    data.kwargs["qd_instrument"] = None
    with pytest.raises(ValueError, match="PRE_FUNDING_STOP_GUARD_REQUIRED"):
        await start.run_accepted_original_paper_session(
            startup=data.kwargs, seconds=120,
        )
    assert data.events == []
    assert data.runtime.state == "STOPPED"


@pytest.mark.asyncio
async def test_non_hl_paper_cannot_inherit_hl_only_funding_proof(monkeypatch):
    data = fixture_ports(monkeypatch)
    data.kwargs["source_lane"] = "QUALITY_DIPS"
    with pytest.raises(ValueError, match="NON_HL_FUNDING_GUARD_SCOPE_REFUSED"):
        await start.run_accepted_original_paper_session(
            startup=data.kwargs, seconds=120,
            intrahour_flat_before_funding=True,
        )
    assert data.events == []
    assert data.runtime.state == "STOPPED"


@pytest.mark.asyncio
async def test_original_hl_preflight_denial_cannot_arm_or_bind_stop(monkeypatch):
    data = fixture_ports(monkeypatch)
    data.kwargs["source_lane"] = "HYPERLIQUID"
    data.kwargs["qd_instrument"] = None

    def refused(_):
        raise ValueError("TEST_ORIGINAL_NATIVE_COST_OR_TIME_REFUSED")

    monkeypatch.setattr(start, "require_original_hl_conservative_start_preflight",
                        refused)
    with pytest.raises(ValueError, match="COST_OR_TIME_REFUSED"):
        await start.run_accepted_original_paper_session(
            startup=data.kwargs, seconds=120,
            intrahour_flat_before_funding=True,
        )
    # Exact selected-image verification occurs before the native fee/time
    # check; neither step can arm, bind, or write a financial account.
    assert data.events == ["selected_source"]
    assert data.runtime.state == "STOPPED"
    assert data.runtime.grant is None


@pytest.mark.asyncio
@pytest.mark.parametrize("source_lane", ["HYPERLIQUID", "BOTH"])
async def test_hl_only_approved_preflight_precedes_all_financial_effects(
        monkeypatch, source_lane):
    from app.services import personal_installed_stop_owner
    data = fixture_ports(monkeypatch)
    data.kwargs["source_lane"] = source_lane
    if source_lane == "HYPERLIQUID":
        data.kwargs["qd_instrument"] = None

    def preflight(received):
        assert received["runtime"] is data.kwargs["runtime"]
        assert received["source_lane"] == source_lane
        assert received["qd_instrument"] == data.kwargs["qd_instrument"]
        assert received["operator"] is data.kwargs["operator"]
        data.events.append("native_hl_fee_funding_preflight")
        return {"financial_paper_start_authorized": False,
                "live_trading_authorized": False}

    async def supervised(*, owner, seconds, interval,
                         intrahour_flat_before_funding):
        assert intrahour_flat_before_funding is True
        return owner.request_stop("SHUTDOWN_FLATTEN")

    monkeypatch.setattr(start, "require_original_hl_conservative_start_preflight",
                        preflight)
    monkeypatch.setattr(personal_installed_stop_owner,
                        "run_personal_installed_owner_session", supervised)
    receipt = await start.run_accepted_original_paper_session(
        startup=data.kwargs, seconds=120,
        intrahour_flat_before_funding=True,
    )
    assert receipt["outcome"]["status"] == "FLATTENED"
    assert data.events[0:3] == [
        "selected_source", "native_hl_fee_funding_preflight", "arm",
    ]
    assert data.events.count("shutdown_flatten") == 1
    assert data.events.index("shutdown_flatten") < data.events.index(
        "issuer_revoke")


@pytest.mark.parametrize("source_lane", ["HYPERLIQUID", "BOTH"])
def test_native_hl_preflight_requires_exact_original_signed_clock_and_cut(
        monkeypatch, source_lane):
    from app.services import unified_native_writer
    from scripts.observation_runtime import personal_local_authority
    from scripts.observation_runtime import personal_version_safe_release_clock
    from app.services import hyperliquid_forward_flat_paper_policy

    # Keep the REAL preflight before the disposable test harness stubs the
    # financial operation. Otherwise a passing test would prove nothing.
    original_conservative_preflight = (
        start.require_original_hl_conservative_start_preflight
    )
    data = fixture_ports(monkeypatch)
    data.kwargs["source_lane"] = source_lane
    if source_lane == "HYPERLIQUID":
        data.kwargs["qd_instrument"] = None
    events = data.events

    class OriginalClock:
        def sample(self):
            events.append("original_utc_sample")
            return {"utc": 1795000600, "uncertainty_ms": 139,
                    "schema": "QD_AUTO_NATIVE_CLOCK_V4"}

        def verify(self, sample):
            events.append("verify_issued_utc")
            return True

    class OriginalOperator:
        runtime_id = "EXACT_DISPOSABLE_TEST"
        def __init__(self, clock):
            self.clock = clock

    class OriginalLane:
        def __init__(self, writer):
            self.writer = writer

        def _verify(self):
            events.append("native_lane_verified")

    class OriginalWriter:
        manifest = {"schema": "TEST_ONLY"}
        def _cut(self):
            events.append("native_writer_cut")
            return {"manifest": self.manifest, "state": {"positions": {}}}

    monkeypatch.setattr(personal_local_authority,
                        "NativePersonalOperatorAuthority", OriginalOperator)
    monkeypatch.setattr(personal_version_safe_release_clock,
                        "NativeVersionSafePaperOperatorClock", OriginalClock)
    monkeypatch.setattr(unified_native_writer,
                        "CanonicalWriterLane", OriginalLane)
    monkeypatch.setattr(personal_version_safe_release_clock,
                        "require_version_safe_release_digest",
                        lambda **_: events.append("selected_release_ntp") or True)
    monkeypatch.setattr(hyperliquid_forward_flat_paper_policy,
                        "require_conservative_original_paper_preflight",
                        lambda **_: {
                            "next_utc_hour": (1795000600 // 3600 + 1) * 3600,
                            "financial_paper_start_authorized": False,
                            "live_trading_authorized": False,
                        })
    clock = OriginalClock()
    writer = OriginalWriter()
    data.kwargs["operator"] = OriginalOperator(clock)
    data.kwargs["clock"] = clock
    data.runtime.lanes = {"HYPERLIQUID": OriginalLane(writer)}
    data.runtime.portfolio = SimpleNamespace(
        writers={"HYPERLIQUID": writer})
    proof = original_conservative_preflight(data.kwargs)
    assert proof["financial_paper_start_authorized"] is False
    assert events == [
        "native_lane_verified", "selected_release_ntp",
        "original_utc_sample", "verify_issued_utc",
        "native_writer_cut", "original_utc_sample", "verify_issued_utc",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("lane", ["BOTH","HYPERLIQUID"])
async def test_any_hl_exposed_original_start_requires_funding_stop_before_financial_arm(
        monkeypatch, lane):
    data = fixture_ports(monkeypatch)
    data.kwargs["source_lane"] = lane
    if lane == "HYPERLIQUID":
        data.kwargs["qd_instrument"] = None
    with pytest.raises(ValueError,match="PRE_FUNDING_STOP_GUARD_REQUIRED"):
        await start.run_accepted_original_paper_session(
            startup=data.kwargs, seconds=300,
            intrahour_flat_before_funding=False,
        )
    assert data.events == []
    assert data.runtime.state == "STOPPED"
    assert data.runtime.grant is None


def test_combined_native_original_start_rejects_fee_preflight_before_arm(
        monkeypatch):
    data=fixture_ports(monkeypatch)
    assert data.kwargs["source_lane"]=="BOTH"
    def refused(scope):
        assert scope["qd_instrument"]["symbol"] == "MSFT"
        assert scope["source_lane"]=="BOTH"
        raise ValueError("TEST_COMBINED_HL_ACTUAL_FUNDING_FEES_UNVERIFIED")
    monkeypatch.setattr(start,"require_original_hl_conservative_start_preflight",
                        refused)
    with pytest.raises(ValueError,match="ACTUAL_FUNDING_FEES_UNVERIFIED"):
        start.start_accepted_original_paper_once(**data.kwargs)
    assert data.events==["selected_source"]
    assert data.runtime.state=="STOPPED"
    assert data.runtime.grant is None
