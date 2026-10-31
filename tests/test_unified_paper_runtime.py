"""Disposable multi-market supervision: no provider, runtime store or process I/O."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from decimal import ROUND_DOWN, localcontext

import pytest
from app.services.paper_financial_replay import digest
from app.services.paper_portfolio_risk import (
    check_portfolio_cut,
    check_portfolio_reducing_exit,
)
from app.services.unified_paper_runtime import (
    UnifiedControlStopBridge,
    UnifiedPaperRuntime,
)

NOW = 1792922400  # Sunday: stocks can be closed while perps continue monitoring.


def policy():
    return {"schema": "ATLAS_PAPER_PORTFOLIO_RISK_V1", "policy_id": "SYNTHETIC_NOT_ACCEPTED",
            "capital_usd": "1000", "max_gross_usd": "200", "max_loss_usd": "5",
            "max_positions": 2, "allocations": {"QUALITY_DIPS": "800", "HYPERLIQUID": "200"}, "max_age": 5,
            "max_perp_leverage": "2"}


def accounts():
    return [{"schema": "ATLAS_PAPER_RISK_CUT_V1", "lane": lane, "epoch": lane,
             "currency": currency, "revision": 0, "head": "synthetic-head", "at": NOW,
             "state": "ACKNOWLEDGED", "allocated_usd": allocation, "committed_usd": "0",
             "positions": [], "pending_operations": [], "conversion_id": "synthetic-conversion"}
            for lane, currency, allocation in (("QUALITY_DIPS", "USD", "800"), ("HYPERLIQUID", "USDC", "200"))]


def perp():
    return {"id": "HYPERLIQUID:1", "instrument_id": "HL:BTC:PERP", "side": "SHORT", "quantity": ".001",
            "gross_usd": "100", "loss_usd": "1", "reserved_usd": "50",
            "derivatives": {"schema": "ATLAS_PERP_RISK_EVIDENCE_V1", "margin_mode": "ISOLATED",
                            "leverage": "2", "max_leverage": "10", "notional": "100", "collateral": "50",
                            "maintenance_margin": "5", "unrealized_pnl": "-2", "funding_cash": "-.1",
                            "fees_cash": ".02", "slippage_cash": ".02", "equity": "47.86",
                            "stress_loss_cash": "1", "funding_complete": True, "fee_schedule_id": "synthetic-maker-taker",
                            "funding_cut": "synthetic-hourly", "mark_id": "synthetic-mark", "book_id": "synthetic-bid-ask"}}


def with_perp():
    rows = accounts()
    rows[1].update(positions=[perp()], committed_usd="50")
    return rows


def test_perp_risk_does_not_equal_stock_cash_and_signed_funding_is_audited():
    result = check_portfolio_cut(policy(), with_perp(), now=NOW)
    assert result["gross_usd"] == "100" and result["loss_usd"] == "1"
    assert result["total_cash"] is None and result["total_equity"] is None


@pytest.mark.parametrize("change", [
    {"funding_complete": False}, {"equity": "48"}, {"margin_mode": "CROSS"},
    {"leverage": "11"}, {"leverage": "2.5"}, {"collateral": "1"},
    {"maintenance_margin": "48"}, {"mark_id": ""}, {"funding_cash": "NaN"},
    {"stress_loss_cash": "50"}, {"stress_loss_cash": "NaN"},
])
def test_unsupported_derivatives_never_treated_as_unleveraged_stock(change):
    rows = with_perp()
    rows[1]["positions"][0]["derivatives"].update(change)
    with pytest.raises((ValueError, ArithmeticError)):
        check_portfolio_cut(policy(), rows, now=NOW)


@pytest.mark.parametrize("change", [
    {"pending_operations": ["unknown"]}, {"state": "UNKNOWN"}, {"at": NOW - 6},
    {"at": NOW + 1}, {"revision": True}, {"currency": "USD"}, {"committed_usd": "0"},
])
def test_incomplete_or_contradictory_financial_cuts_refuse(change):
    rows = with_perp()
    rows[1].update(change)
    with pytest.raises(ValueError):
        check_portfolio_cut(policy(), rows, now=NOW)


def test_capital_not_double_allocated_and_exposure_cannot_net():
    p = policy()
    p["allocations"]["HYPERLIQUID"] = "1000"
    with pytest.raises(ValueError, match="ALLOCATED_TWICE"):
        check_portfolio_cut(p, accounts(), now=NOW)
    rows = with_perp()
    p = policy()
    p["max_gross_usd"] = "99"
    with pytest.raises(ValueError, match="GLOBAL_LIMIT"):
        check_portfolio_cut(p, rows, now=NOW)


def test_portfolio_math_uses_fixed_context_and_refuses_rounded_limits():
    with localcontext() as context:
        context.prec, context.rounding = 6, ROUND_DOWN
        assert check_portfolio_cut(policy(), with_perp(), now=NOW)["gross_usd"] == "100"
    rows = with_perp()
    rows[1]["positions"][0]["gross_usd"] = "200.00000000000000000000000001"
    with pytest.raises(ValueError):
        check_portfolio_cut(policy(), rows, now=NOW)


def test_entry_cap_remains_enforced_while_acknowledged_position_can_be_reduced():
    before, after = accounts(), accounts()
    before[0].update(committed_usd="100", positions=[{
        "id": "QUALITY_DIPS:one", "instrument_id": "US:STOCK:ONE", "side": "LONG", "quantity": "1",
        "gross_usd": "110", "loss_usd": "2", "reserved_usd": "100", "derivatives": None}])
    with pytest.raises(ValueError, match="STOCK_LIMIT"):
        check_portfolio_cut(policy(), before, now=NOW)
    assert check_portfolio_reducing_exit(policy(), before, after, now=NOW)["positions"] == 0
    with pytest.raises(ValueError, match="ACCOUNT_SUBSTITUTION"):
        check_portfolio_reducing_exit(policy(), after, before, now=NOW)


def test_margin_warning_does_not_authorize_entry_or_prevent_a_proven_full_exit():
    before = with_perp()
    before[1]["positions"][0]["derivatives"]["maintenance_margin"] = "48"
    with pytest.raises(ValueError, match="LIQUIDATION"):
        check_portfolio_cut(policy(), before, now=NOW)
    assert check_portfolio_reducing_exit(policy(), before, accounts(), now=NOW)["positions"] == 0


class Lane:
    def __init__(self, name, *, closed=False, failed=False):
        self.name, self.closed, self.failed = name, closed, failed
        self.calls, self.stops = [], 0

    async def observe(self):
        if self.failed:
            raise OSError("synthetic unavailable")
        return {"lane": self.name, "at": NOW, "connection": "CONNECTED",
                "session": "CLOSED" if self.closed else "OPEN", "signal": None, "source": "SYNTHETIC"}

    def verify_observation(self, value):
        return value["source"] == "SYNTHETIC"

    def dispatch(self, proposal, reservation):
        self.calls.append(proposal)
        return {"state": "ACKNOWLEDGED", "operation_id": proposal["operation_id"]}

    def verify_proposal(self, proposal, observation):
        return proposal.get("operation_id") != "forged"

    def stop(self, *, emergency):
        self.stops += 1
        return {"state": "POSITION_OPEN" if self.failed or emergency else "ACKNOWLEDGED_FLAT_AND_DRAINED"}


class Installation:
    valid = True

    def __init__(self):
        self.snapshot = {"test_only": True}

    @contextmanager
    def lease(self, request):
        yield self

    def check_components(self, components):
        return self.valid

    def check(self, snapshot):
        return self.valid


class Custody:
    def __init__(self):
        self.policy, self.before, self.projected = policy(), accounts(), with_perp()
        self.operations = {}
        self.fail_ack = False

    def verify_restart(self, grant):
        return all(v["state"] == "ACKNOWLEDGED" for v in self.operations.values())

    @contextmanager
    def lease(self, request):
        yield self

    def verify(self, request):
        return True

    def reserve(self, request):
        key = request["proposal"]["operation_id"]
        if key in self.operations:
            old = self.operations[key]
            if old["binding"] != digest(request):
                raise ValueError("SYNTHETIC_CONFLICT")
            return {**old, "state": "ACKNOWLEDGED" if old["state"] == "ACKNOWLEDGED" else "UNKNOWN"}
        result = {"state": "RESERVED", "binding": digest(request)}
        self.operations[key] = deepcopy(result)
        return result

    def verify_receipt(self, request, receipt):
        return receipt["state"] == "ACKNOWLEDGED"

    def acknowledge(self, request, receipt):
        if self.fail_ack:
            return False
        self.operations[request["proposal"]["operation_id"]]["state"] = "ACKNOWLEDGED"
        return True

    def replay(self, request, reservation):
        return {"state": "ACKNOWLEDGED", "operation_id": request["proposal"]["operation_id"]}


def runtime(**kwargs):
    ports = {"QUALITY_DIPS": Lane("QUALITY_DIPS", closed=True), "HYPERLIQUID": Lane("HYPERLIQUID")}
    r = UnifiedPaperRuntime(lanes=ports, installation=Installation(), portfolio=Custody(), clock=lambda: NOW)
    r.start({"test_only": True})
    return r


@pytest.mark.asyncio
async def test_weekend_zero_signals_remains_running_and_perps_monitor():
    r = runtime()
    view = await r.poll()
    assert view["state"] == "RUNNING"
    assert view["lanes"]["QUALITY_DIPS"]["session"] == "CLOSED"
    assert view["lanes"]["HYPERLIQUID"]["session"] == "OPEN"
    assert all(not lane.calls for lane in r.lanes.values())


@pytest.mark.asyncio
async def test_one_feed_failure_does_not_disrupt_other_monitor():
    r = runtime()
    r.lanes["HYPERLIQUID"].failed = True
    view = await r.poll()
    assert view["lanes"]["HYPERLIQUID"]["connection"] == "UNAVAILABLE"
    assert view["lanes"]["QUALITY_DIPS"]["connection"] == "CONNECTED"
    with pytest.raises(ValueError, match="CURRENT_LANE"):
        r.dispatch("HYPERLIQUID", {"operation_id": "one", "kind": "ENTRY"})


@pytest.mark.asyncio
async def test_duplicate_entry_receipt_never_repeats_financial_callback():
    r = runtime()
    await r.poll()
    p = {"operation_id": "one", "kind": "ENTRY"}
    assert r.dispatch("HYPERLIQUID", p) == r.dispatch("HYPERLIQUID", p)
    assert len(r.lanes["HYPERLIQUID"].calls) == 1


@pytest.mark.asyncio
async def test_unknown_ack_blocks_dispatch_restart_and_clean_stop():
    r = runtime()
    await r.poll()
    r.portfolio.fail_ack = True
    with pytest.raises(ValueError, match="UNCERTAIN"):
        r.dispatch("HYPERLIQUID", {"operation_id": "one", "kind": "ENTRY"})
    with pytest.raises(ValueError):
        r.dispatch("HYPERLIQUID", {"operation_id": "two", "kind": "ENTRY"})
    assert r.stop()["state"] == "STOP_INCOMPLETE"
    other = UnifiedPaperRuntime(lanes=r.lanes, installation=r.installation, portfolio=r.portfolio, clock=r.clock)
    with pytest.raises(ValueError, match="RESTART"):
        other.start({"test_only": True})
    assert len(r.lanes["HYPERLIQUID"].calls) == 1


@pytest.mark.asyncio
async def test_pause_closed_market_and_stop_preserve_admission_barriers():
    r = runtime()
    await r.poll()
    with pytest.raises(ValueError, match="CURRENT_LANE"):
        r.dispatch("QUALITY_DIPS", {"operation_id": "stock", "kind": "ENTRY"})
    r.pause()
    with pytest.raises(ValueError, match="ADMISSION"):
        r.dispatch("HYPERLIQUID", {"operation_id": "one", "kind": "ENTRY"})
    result = r.stop()
    assert result == r.stop() and not result["auto_resume"]
    assert all(lane.stops == 1 for lane in r.lanes.values())
    with pytest.raises(ValueError):
        r.start({"test_only": True})


def test_default_refusal_and_component_substitution():
    with pytest.raises(ValueError):
        UnifiedPaperRuntime()
    r = runtime()
    r.installation.valid = False
    with pytest.raises(ValueError, match="UNVERIFIED"):
        r.dispatch("HYPERLIQUID", {"operation_id": "one", "kind": "ENTRY"})


@pytest.mark.asyncio
async def test_concurrent_retries_and_stop_never_repeat_callbacks():
    r = runtime()
    await r.poll()
    proposal = {"operation_id": "one", "kind": "ENTRY"}
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: r.dispatch("HYPERLIQUID", proposal), range(8)))
    assert all(v == results[0] for v in results)
    assert len(r.lanes["HYPERLIQUID"].calls) == 1
    with ThreadPoolExecutor(max_workers=4) as pool:
        stops = list(pool.map(lambda _: r.stop(), range(8)))
    assert all(v == stops[0] for v in stops)
    assert all(p.stops == 1 for p in r.lanes.values())


@pytest.mark.asyncio
async def test_no_strategy_proof_no_dispatch_and_stale_read_is_not_current():
    r = runtime()
    await r.poll()
    with pytest.raises(ValueError, match="STRATEGY"):
        r.dispatch("HYPERLIQUID", {"operation_id": "forged", "kind": "ENTRY"})
    r.clock = lambda: NOW + 6
    view = r.read_snapshot()
    assert all(v["connection"] == "STALE" for v in view["lanes"].values())
    assert all(not p.calls for p in r.lanes.values())


@pytest.mark.asyncio
async def test_continuous_no_signal_monitoring_and_bounded_expiry():
    r = runtime()
    calls = []
    async def next_proposal(observation):
        calls.append(observation["lane"])
    r.lanes["HYPERLIQUID"].next_proposal = next_proposal
    result = await r.run(seconds=.15, interval=.05)
    assert len(calls) >= 2 and set(calls) == {"HYPERLIQUID"}
    assert result["state"] == "PAUSED" and all(not p.calls for p in r.lanes.values())


@pytest.mark.asyncio
async def test_existing_authenticated_control_transport_stops_both_lanes_once():
    import httpx
    from app.services.quality_dips_stop_bridge import register_stop_routes
    from fastapi import FastAPI

    r = runtime()
    await r.poll()
    bridge = UnifiedControlStopBridge(r)
    app = FastAPI()
    origin, token = "http://127.0.0.1:18799", "synthetic-test-control-token-only-1234"
    register_stop_routes(app, bridge=bridge, origin=origin, token=token)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=origin) as client:
        assert (await client.post("/_atlas/control/stop", json={"mode": "SHUTDOWN_FLATTEN"})).status_code == 403
        headers = {"origin": origin, "x-atlas-control": token}
        for _ in range(2):
            result = await client.post("/_atlas/control/stop", headers=headers, json={"mode": "SHUTDOWN_FLATTEN"})
            assert result.status_code == 200
            assert result.json()["schema"] == "QD_CONTROL_STOP_V1"
            assert result.json()["outcome"]["status"] == "FLATTENED"
    assert r.entry_closed.is_set() and all(p.stops == 1 for p in r.lanes.values())


@pytest.mark.parametrize("emergency", [True, False])
def test_unified_control_incomplete_or_emergency_never_claims_flat(emergency):
    r = runtime()
    r.lanes["HYPERLIQUID"].failed = True
    result = UnifiedControlStopBridge(r).request_stop("EMERGENCY" if emergency else "SHUTDOWN_FLATTEN")
    assert result["outcome"]["status"] == "SHUTDOWN_INCOMPLETE"
    assert result["outcome"]["position_state"] == "POSITION_OPEN"
    assert all(p.stops == 1 for p in r.lanes.values())
