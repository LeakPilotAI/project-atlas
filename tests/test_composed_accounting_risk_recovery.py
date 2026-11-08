"""AIP-06 offline slice: real accounting, synthetic ports, no native acceptance.

These tests compose existing components; they do not authenticate their fixture
inputs or measure NTFS publication/installed Stop. Native proof remains separate.
"""

import copy
from contextlib import closing
from types import SimpleNamespace

import pytest
from app.services.paper_epoch_fixture import EpochFixture, create_epoch_fixture
from app.services.paper_financial_audit import audit_financial_events
from app.services.paper_financial_replay import (
    body,
    event_stream_record,
    number,
    replay_verified_events,
)
from app.services.unified_paper_runtime import UnifiedPaperRuntime
from test_perp_financial_v2 import entry as perp_entry
from test_perp_financial_v2 import exit_command, funding
from test_perp_financial_v2 import manifest as perp_manifest
from test_personal_commissioning_runner import setup as runner_fixture
from test_personal_paper_inception_memory import system as inception_fixture
from test_quality_dips_autonomous_paper import candidate, entry, monitor
from test_quality_dips_autonomous_paper import setup as qd_fixture
from test_unified_paper_runtime import runtime as unified_fixture


def verified(store):
    """Independently audit each durable SQLite fixture cut, including on reopen."""
    with closing(store.connect(readonly=True)) as db:
        rows = [event_stream_record(*r) for r in db.execute("SELECT * FROM events ORDER BY revision")]
    state = store.snapshot()
    replay, head, operations = replay_verified_events(store.manifest, rows)
    assert all(state[k] == v for k, v in replay.items())
    audit = audit_financial_events(store.manifest, rows, state)
    assert audit["source_revision"] == state["revision"] == len(operations)
    assert not state["startup_authorized"] and not state["shutdown_authorized"]
    return {"snapshot": state, "head": head, "rows": rows}


@pytest.fixture
def pair(tmp_path):
    qd = qd_fixture(tmp_path)
    perp = create_epoch_fixture(tmp_path / "separate-usdc.sqlite", perp_manifest())
    return qd, perp


def test_interleaved_partial_full_funding_restart_cuts_are_exact(pair, record_property):
    qd, perp = pair
    b = candidate(qd)
    assert entry(qd)["filled"]
    first = verified(qd.ledger)
    assert number(first["snapshot"]["cash"]) == number("899.9600")
    ack = perp.execute(perp_entry())
    assert perp.execute(perp_entry()) == ack
    assert verified(qd.ledger) == first
    perp.execute(exit_command(perp, "0.2"))
    before_funding = verified(perp)
    assert monitor(qd, b, "partial", "110", {"fundamentals_score": 60})["filled"]
    partial = verified(qd.ledger)
    assert number(next(iter(partial["snapshot"]["positions"].values()))["remaining"]) == number("0.6")
    assert verified(perp) == before_funding

    # A reconstructed QD engine cannot dispatch automatically. Perp receipt
    # replay is still idempotent after its fixture store is reopened.
    restarted = qd.new()
    assert restarted.grant is None and restarted.dispatch_closed
    assert not entry(SimpleNamespace(**{**vars(qd), "engine": restarted}))["filled"]
    assert verified(qd.ledger) == partial
    perp = EpochFixture(perp.path, expected_manifest=perp.manifest)
    funding_command = funding(perp)
    funding_ack = perp.execute(funding_command)
    assert perp.execute(funding_command) == funding_ack
    with pytest.raises(ValueError, match="Conflicting operation replay"):
        perp.execute(funding(perp))  # Regenerated expected revisions are a conflict.
    assert verified(qd.ledger) == partial
    assert monitor(qd, b, "full", "120", {"classification": "THESIS_BROKEN"})["filled"]
    perp.execute(exit_command(perp, "0.3", 7202, "final", "104"))
    qcut, pcut = verified(qd.ledger), verified(perp)
    assert qcut["snapshot"]["revision"] == 3 and pcut["snapshot"]["revision"] == 4
    assert number(qcut["snapshot"]["cash"]) == number("1015.9136")
    assert number(qcut["snapshot"]["costs"]) == number("0.0864")
    assert number(pcut["snapshot"]["cash"]) == number("1001.52936")
    assert number(pcut["snapshot"]["funding"]) == number("-0.03")
    assert number(pcut["snapshot"]["reserved_margin"]) == 0
    assert all(number(p["remaining"]) == 0 for c in (qcut, pcut) for p in c["snapshot"]["positions"].values())
    assert qd.engine.stop() == "STOPPED"
    assert verified(EpochFixture(qd.ledger.path, expected_manifest=qd.m)) == qcut
    assert verified(EpochFixture(perp.path, expected_manifest=perp.manifest)) == pcut
    record_property("disposable_cuts", body({
        "domain": "DISPOSABLE", "USD": {"revision": 3, "cash": "1015.9136", "head": qcut["head"]},
        "USDC": {"revision": 4, "cash": "1001.52936", "head": pcut["head"]},
        "native_stop_proved": False, "operational_authority": False,
    }))


def test_realized_session_loss_refuses_new_perp_entry_without_touching_usd(pair):
    qd, perp = pair
    assert entry(qd)["filled"]
    usd = verified(qd.ledger)
    perp.execute(perp_entry())
    perp.execute(funding(perp, rate="0.04"))
    perp.execute(exit_command(perp, "0.5", 7202, "loss-close", "100"))
    lost = verified(perp)
    assert number(lost["snapshot"]["net_r"]) < number("-3")
    command = perp_entry(op="after-loss")
    command.update(expected_source_revision=lost["snapshot"]["revision"], timestamp=7203)
    command["evidence"].update(observed_at=7203, sequence="after-loss")
    with pytest.raises(ValueError):
        perp.execute(command)
    assert verified(perp) == lost and verified(qd.ledger) == usd


@pytest.mark.parametrize("lane", ["QUALITY_DIPS", "HYPERLIQUID"])
@pytest.mark.parametrize("damage", ["receipt", "digest", "revision", "foreign-manifest", "projection"])
def test_one_account_corruption_never_contaminates_other_account(pair, lane, damage):
    qd, perp = pair
    assert entry(qd)["filled"]
    perp.execute(perp_entry())
    bad, good = (qd.ledger, perp) if lane == "QUALITY_DIPS" else (perp, qd.ledger)
    good_cut = verified(good)
    if damage == "foreign-manifest":
        with pytest.raises(ValueError):
            EpochFixture(bad.path, expected_manifest=good.manifest).snapshot()
    else:
        with closing(bad.connect()) as db, db:
            if damage == "receipt":
                db.execute("UPDATE events SET receipt='{}'")
            elif damage == "digest":
                db.execute("UPDATE events SET digest=?", ("0" * 64,))
            elif damage == "revision":
                db.execute("UPDATE events SET revision=2")
            else:
                db.execute("INSERT INTO projections VALUES('unacknowledged','synthetic',NULL)")
        with pytest.raises((ValueError, KeyError)):
            if damage == "projection":
                bad.daily_report("2026-10-26" if lane == "QUALITY_DIPS" else "1970-01-01")
            else:
                verified(EpochFixture(bad.path, expected_manifest=bad.manifest))
    assert verified(good) == good_cut


@pytest.mark.parametrize("lane", ["QUALITY_DIPS", "HYPERLIQUID"])
@pytest.mark.parametrize("failure", ["inception.json", "scope.json", "0001-report.json", "readback"])
def test_interrupted_inception_and_restart_never_repeat_other_lane(lane, failure):
    other = "HYPERLIQUID" if lane == "QUALITY_DIPS" else "QUALITY_DIPS"
    failed, healthy = inception_fixture(lane, failure), inception_fixture(other)
    try:
        healthy.pub.publish()
        healthy_cut = copy.deepcopy(healthy.files.values)
        with pytest.raises((ValueError, OSError)):
            failed.pub.publish()
        failed_cut = copy.deepcopy(failed.files.values)
        assert failed.custody.row(failed.b.scope()["operation_id"])[2] == "UNKNOWN"
        with pytest.raises(ValueError):
            failed.pub.publish()
        assert failed.files.values == failed_cut and healthy.files.values == healthy_cut
        assert healthy.custody.row(healthy.b.scope()["operation_id"])[2] == "ACKNOWLEDGED"
        assert failed.m["currency"] != healthy.m["currency"]
    finally:
        failed.ledger.db.close()
        healthy.ledger.db.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["ack", "provider", "clock", "positions", "exposure", "pending"])
async def test_composed_admission_failure_and_restart_keep_global_barrier(fault):
    # Existing explicit in-memory installation/custody ports, NOT native proof.
    r = unified_fixture()
    await r.poll()
    proposal = {"operation_id": "SYNTHETIC-COMPOSED-" + fault, "kind": "ENTRY"}
    if fault == "ack":
        r.portfolio.fail_ack = True
    elif fault == "provider":
        r.lanes["HYPERLIQUID"].failed = True
        await r.poll()
    elif fault == "clock":
        r.clock = lambda: 1792922406
    elif fault == "positions":
        r.portfolio.policy["max_positions"] = 0
    elif fault == "exposure":
        r.portfolio.policy["max_gross_usd"] = "99"
    else:
        r.portfolio.before[0]["pending_operations"] = ["UNKNOWN"]
    with pytest.raises(ValueError):
        r.dispatch("HYPERLIQUID", proposal)
    assert not r.lanes["QUALITY_DIPS"].calls
    assert len(r.lanes["HYPERLIQUID"].calls) == int(fault == "ack")
    before = copy.deepcopy(r.portfolio.operations)
    if fault == "ack":
        assert r.stop()["state"] == "STOP_INCOMPLETE"
        other = UnifiedPaperRuntime(lanes=r.lanes, installation=r.installation, portfolio=r.portfolio, clock=r.clock)
        with pytest.raises(ValueError, match="RESTART"):
            other.start({"test_only": True})
    else:
        assert not before  # No reservation or writer reached.
    assert r.portfolio.operations == before


@pytest.mark.parametrize("phase,count,accepted", [
    ("RUN", 126, True), ("RUN", 127, False), ("STOP", 127, True), ("STOP", 128, False),
])
@pytest.mark.parametrize("resource", ["source", "reports"])
def test_stop_capacity_boundary_remains_reserved(phase, count, accepted, resource):
    s = runner_fixture()
    # Reports reserve five during RUN and three during STOP, versus two/one
    # source entries. Check exact existing bounds, without a native write.
    if resource == "reports":
        count -= 3 if phase == "RUN" else 2
    key = "entries" if resource == "source" else "reports"
    s.cut[resource][key] = [{}] * count
    if accepted:
        s.runner._budget(phase)
    else:
        with pytest.raises(ValueError, match="CAPACITY"):
            s.runner._budget(phase)
    assert "start" not in s.calls and "stop" not in s.calls
