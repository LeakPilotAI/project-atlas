from decimal import Decimal

import pytest
from app.investment.quality_dips_paper import open_lot, read_events
from app.services.paper_epoch_fixture import EpochFixture, create_epoch_fixture
from app.services.paper_portfolio_fixture import account_summary_fixture
from app.services.paper_strategy_fixture import (
    NativeProjectionFixture,
    exit_command,
    quality_entry,
    quality_terminal_exit,
)
from app.services.paper_workflow_fixture import (
    NativePerpProjectionFixture,
    quality_signal_fixture,
)
from app.trading_core.perp_manual_state_store import ManualPerpStateStore
from test_hyperliquid_paper_handoff import actual_journal, open_actual
from test_paper_epoch_fixture import STAMP, entry, manifest, quote
from test_paper_strategy_fixture import native_bridge


def test_foreign_native_write_refused_before_new_financial_commit(tmp_path):
    store, bridge, _, manual = native_bridge(tmp_path)
    receipt = bridge.apply(entry(store))["evidence"]["canonical_receipt"]
    state = manual.load()
    manual.save(plans=state["plans"], setup_history=[{"foreign_fixture_writer": True}])
    command = exit_command(store, operation_id="exit", position_id=receipt["position_id"], quantity="0.5",
                           quote=quote("104"), timestamp=STAMP, manual=True)
    with pytest.raises(ValueError, match="Changed native"):
        bridge.apply(command)
    assert store.snapshot()["revision"] == 1


def signal_inputs(**changes):
    return {"symbol": "MSFT", "current_price": 100,
            "normalization": {"conservative": 100, "base": 140, "optimistic": 180},
            "quality_score": 82, "fundamentals_score": 80, "valuation_score": 72,
            "drawdown_percentile": 80, "evidence_quality": "HIGH", "thesis_intact": True,
            "value_trap": False, **changes}


def q7_native(tmp_path):
    store = create_epoch_fixture(tmp_path / "account.sqlite", manifest("q7-perps"))
    module, journal = actual_journal(tmp_path)
    manual = ManualPerpStateStore(tmp_path / "manual.json")
    manual.save(plans=[], setup_history=[])
    publisher = NativePerpProjectionFixture(journal=journal, journal_path=module.JOURNAL_PATH, manual_store=manual)
    bridge = NativeProjectionFixture(store, publish=publisher.publish, observe=publisher.observe,
                                     initial_observation_digest=publisher.expected_observation)
    return store, bridge, module, manual


def test_actual_quality_signal_to_cash_report_restart_preserves_legacy(tmp_path):
    legacy = tmp_path / "legacy-quality.jsonl"
    open_lot({"symbol": "MSFT", "observation_id": "retained-legacy-fixture", "price": 100},
             level="L1", paper_notional_dollars=100, path=legacy)
    original = legacy.read_bytes()
    m = manifest("q7-quality", "QUALITY_DIPS")
    store = create_epoch_fixture(tmp_path / "account.sqlite", m)
    signal = quality_signal_fixture(signal_inputs(), quote=quote("100", "MSFT"), observation_id="q7-obs")
    assert signal["classification"] == "ACCUMULATION" and "L1" in signal["reached_levels"]
    command = quality_entry(store, signal, level="L1", notional="100", operation_id="entry", timestamp=STAMP, manual=True)
    ack = store.execute(command)
    assert store.execute(command) == ack and Decimal(store.snapshot()["cash"]) == 900
    pos = ack["position_id"]
    partial = exit_command(store, operation_id="partial", position_id=pos, quantity="0.25",
                           quote=quote("110", "MSFT"), timestamp=STAMP, manual=True)
    store.execute(partial)
    assert store.execute(partial)["source_revision"] == 2
    assert Decimal(store.snapshot()["positions"][pos]["remaining"]) == Decimal("0.75")
    first = store.daily_report("2026-10-23")
    assert first["state"] == "INCOMPLETE"
    final = quality_terminal_exit(store, position_id=pos, operation_id="final", terminal_observation={"classification": "THESIS_BROKEN"},
                                  quote=quote("120", "MSFT"), timestamp=STAMP, manual=True)
    receipt = store.execute(final)
    restarted = EpochFixture(store.path, expected_manifest=m)
    assert restarted.execute(final) == receipt
    report = restarted.daily_report("2026-10-23")
    assert Decimal(report["closing_cash"]) == Decimal("1017.42")
    assert Decimal(report["costs"]) == Decimal("0.08") and Decimal(report["realized_net"]) == Decimal("17.42")
    assert account_summary_fixture(restarted, now=STAMP, max_age=30)["state"] == "RECONCILED_FIXTURE_ONLY"
    assert legacy.read_bytes() == original and read_events(legacy)[0]["status"] == "OPEN"
    with store.connect(readonly=True) as db:
        assert db.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 3
        assert db.execute("SELECT COUNT(*) FROM daily").fetchone()[0] == 2


@pytest.mark.parametrize("bad", ["weak", "thesis", "mismatch"])
def test_quality_actual_policy_blocks_ineligible_entry(tmp_path, bad):
    store = create_epoch_fixture(tmp_path / "account.sqlite", manifest("quality", "QUALITY_DIPS"))
    inputs = signal_inputs(evidence_quality="LOW") if bad == "weak" else signal_inputs(thesis_intact=False) if bad == "thesis" else signal_inputs()
    with pytest.raises(ValueError):
        signal = quality_signal_fixture(inputs, quote=quote("101" if bad == "mismatch" else "100", "MSFT"), observation_id="obs")
        store.execute(quality_entry(store, signal, level="L1", notional="100", operation_id="entry", timestamp=STAMP, manual=True))
    assert store.snapshot()["revision"] == 0


def test_actual_three_asset_manual_workflow_report_and_restart(tmp_path):
    store, bridge, module, manual = q7_native(tmp_path)
    ids = {}
    for symbol in ("BTC", "ETH", "SOL"):
        c = entry(store, symbol, symbol)
        if symbol == "ETH": c["side"] = "SHORT"
        ack = bridge.apply(c)
        assert bridge.apply(c) == ack
        ids[symbol] = ack["evidence"]["canonical_receipt"]["position_id"]
    retained_native = module.JOURNAL_PATH.read_bytes()
    for symbol, pos in ids.items():
        for name, qty, price in [("partial", "0.125", "98" if symbol == "ETH" else "102"),
                                 ("final", "0.375", "96" if symbol == "ETH" else "104")]:
            c = exit_command(store, operation_id=symbol + name, position_id=pos, quantity=qty,
                             quote=quote(price, symbol), timestamp=STAMP, manual=True)
            assert bridge.apply(c) == bridge.apply(c)
    assert Decimal(bridge.daily_report("2026-10-23")["closing_cash"]) == Decimal("1005.13")
    restarted = EpochFixture(store.path, expected_manifest=manifest("q7-perps"))
    publisher = NativePerpProjectionFixture(journal=module.PaperJournal(), journal_path=module.JOURNAL_PATH, manual_store=manual)
    reader = NativeProjectionFixture(restarted, publish=publisher.publish, observe=publisher.observe)
    summary = account_summary_fixture(restarted, reader=reader, now=STAMP, max_age=30)
    assert summary["state"] == "RECONCILED_FIXTURE_ONLY" and summary["remaining_positions"] == []
    assert Decimal(summary["realized_net"]) == Decimal("5.13")
    assert module.JOURNAL_PATH.read_bytes() == retained_native and len(module.PaperJournal().list_open()) == 3
    assert all(p["status"] == "ENTERED" for p in manual.load()["plans"])


@pytest.mark.parametrize("fault_at", ["before_projection", "after_projection"])
def test_q7_unknown_publication_never_replays_or_reports(tmp_path, fault_at):
    store, bridge, _, _ = q7_native(tmp_path)
    c = entry(store)
    def fault(phase):
        if phase == fault_at: raise RuntimeError("fixture interrupted")
    with pytest.raises(RuntimeError): bridge.apply(c, fault=fault)
    with pytest.raises(ValueError, match="UNKNOWN"): bridge.apply(c)
    summary = account_summary_fixture(store, reader=bridge, now=STAMP, max_age=30)
    assert summary["state"] == "UNKNOWN" and summary["reconciled_cash"] is None
    with pytest.raises(ValueError): bridge.daily_report("2026-10-23")


def test_native_independent_interference_during_publication_preserves_unknown(tmp_path):
    store, bridge, _, manual = q7_native(tmp_path)
    c = entry(store)
    def interference(phase):
        if phase == "before_projection": manual.save(plans=[], setup_history=[{"setup_key": "foreign"}])
    with pytest.raises(ValueError, match="Changed native"): bridge.apply(c, fault=interference)
    assert store.snapshot()["revision"] == 1 and store.snapshot()["pending_projections"] == 1
    assert account_summary_fixture(store, reader=bridge, now=STAMP, max_age=30)["state"] == "UNKNOWN"


def test_changed_initial_native_fixture_refuses_before_financial_entry(tmp_path):
    store, bridge, _, manual = q7_native(tmp_path)
    manual.save(plans=[], setup_history=[{"setup_key": "foreign"}])
    with pytest.raises(ValueError, match="Changed native initial"): bridge.apply(entry(store))
    assert store.snapshot()["revision"] == 0


def test_preexisting_unassociated_native_position_is_not_adopted(tmp_path):
    module, journal = actual_journal(tmp_path)
    open_actual(journal)
    original = module.JOURNAL_PATH.read_bytes()
    manual = ManualPerpStateStore(tmp_path / "manual.json")
    manual.save(plans=[], setup_history=[])
    with pytest.raises(ValueError, match="Unassociated"):
        NativePerpProjectionFixture(journal=journal, journal_path=module.JOURNAL_PATH, manual_store=manual)
    assert module.JOURNAL_PATH.read_bytes() == original and len(journal.list_open()) == 1
