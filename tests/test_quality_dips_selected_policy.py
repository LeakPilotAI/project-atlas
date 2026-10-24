"""Synthetic evidence pins are test authority only, never operational consent."""
import copy
import json
from pathlib import Path

import pytest
from app.services import paper_financial_replay as finance
from app.services.paper_epoch_fixture import EpochFixture, create_epoch_fixture
from app.services.paper_financial_audit import audit_financial_events


def setup_case(symbol="MSFT", asset="STOCK", rank_order=1):
    golden = json.loads((Path(__file__).parent / "fixtures/fs1/legacy-synthetic-golden.json").read_text(encoding="utf-8"))["cases"][0]
    manifest = copy.deepcopy(golden["manifest"])
    manifest.update(schema="PAPER_EPOCH_SELECTED_QD_V2", opening_cash="1000", initial_net_r="0", fees_bps="2", slippage_bps="2")
    timestamp = manifest["opened_at"] + 10
    rank = {'symbol': symbol, 'instrument_id': "synthetic:" + symbol, 'observation_id': "obs:" + symbol, 'level': "L1", 'rank': rank_order, 'ranked_at': timestamp, 'source_id': "synthetic-ranking", 'revision': 1, 'strategy_version': "QUALITY_DIPS_V3", 'policy_version': "quality-dips-v3-mos-15-20-25-30-v1", 'evidence_class': "FORWARD_COLLECTION", 'classification': "ACCUMULATION", 'reached_levels': ["L1"]}
    manifest["account_policy"] = {'schema': "QD_SELECTED_ACCOUNT_POLICY_V1", 'evidence_scope': "DISPOSABLE_ONLY", 'max_entry_usd': "100", 'max_positions': 1, 'ranking_max_age_seconds': 600, 'instruments': {symbol: {'instrument_id': rank["instrument_id"], 'asset_class': asset, 'fractional': True, 'quote_source': "synthetic-price"}}, 'ranking_receipts': [finance.digest(rank)]}
    command = {'schema': "PAPER_COMMAND_SELECTED_QD_V2", 'epoch': manifest["epoch"], 'operation_id': "entry", 'kind': "ENTRY", 'expected_source_revision': 0, 'timestamp': timestamp, 'manual': True, 'quote': {'symbol': symbol, 'price': "40", 'observed_at': timestamp, 'source_id': "synthetic-price"}, 'symbol': symbol, 'side': "LONG", 'quantity': "2.5", 'risk_price': None, 'origin_ref': rank["observation_id"] + ":L1", 'eligibility': {'instrument_id': rank["instrument_id"], 'ranking': rank}}
    return manifest, command


def exit_command(manifest, entry, state, quantity, operation="exit", elapsed=1):
    ident, p = next(iter(state["positions"].items()))
    return {'schema': "PAPER_COMMAND_SELECTED_QD_V2", 'epoch': manifest["epoch"], 'operation_id': operation, 'kind': "EXIT", 'expected_source_revision': state["revision"], 'timestamp': state["last_clock"] + elapsed, 'manual': True, 'quote': {'symbol': p["symbol"], 'price': "44", 'observed_at': state["last_clock"] + elapsed, 'source_id': "synthetic-price"}, 'position_id': ident, 'quantity': quantity, 'expected_position_revision': p["revision"], 'eligibility': {"instrument_id": entry["eligibility"]["instrument_id"]}}


@pytest.mark.parametrize("symbol,asset", [("MSFT", "STOCK"), ("AAPL", "STOCK"), ("SPY", "ETF"), ("QQQ", "ETF")])
def test_distinct_ranked_instruments_replay_partial_exit_and_overnight(symbol, asset, tmp_path):
    m, c = setup_case(symbol, asset)
    store = create_epoch_fixture(tmp_path / "fixture.sqlite", m)
    receipt = store.execute(c)
    assert receipt["schema"] == "PAPER_RECEIPT_SELECTED_QD_V2"
    assert receipt["payload_digest"] == finance.digest(c)
    assert not receipt["startup_authorized"]
    assert store.execute(c) == receipt
    state = store.snapshot()
    partial = exit_command(m, c, state, "1", elapsed=86400)
    store.execute(partial)
    assert next(iter(store.snapshot()["positions"].values()))["remaining"] == "1.5"
    final = exit_command(m, c, store.snapshot(), "1.5", "final")
    store.execute(final)
    restarted = EpochFixture(store.path, expected_manifest=m)
    assert restarted.snapshot() == store.snapshot()
    assert next(iter(restarted.snapshot()["positions"].values()))["remaining"] == "0.0"
    with store.connect(readonly=True) as db:
        records = [finance.event_stream_record(*row) for row in db.execute("SELECT * FROM events ORDER BY revision")]
    assert audit_financial_events(m, records, store.snapshot())["source_revision"] == 3


@pytest.mark.parametrize("damage", ["missing", "unranked", "stale-rank", "future-rank", "stale-price", "foreign-source",
    "unsupported", "fractional", "manual", "limit", "rounding-limit", "identity", "signal", "short", "version"])
def test_refusal_before_financial_publication(damage, tmp_path):
    m, c = setup_case()
    p = m["account_policy"]
    if damage == "missing": c.pop("eligibility")
    if damage == "unranked": c["eligibility"]["ranking"]["rank"] = 2
    if damage in ("stale-rank", "future-rank"):
        c["eligibility"]["ranking"]["ranked_at"] += -601 if damage == "stale-rank" else 1
        p["ranking_receipts"] = [finance.digest(c["eligibility"]["ranking"])]
    if damage == "stale-price": c["quote"]["observed_at"] -= 31
    if damage == "foreign-source": c["quote"]["source_id"] = "foreign"
    if damage == "unsupported": p["instruments"]["MSFT"]["asset_class"] = "PERPETUAL"
    if damage == "fractional": p["instruments"]["MSFT"]["fractional"] = False
    if damage == "manual": c["manual"] = False
    if damage == "limit": c["quantity"] = "2.51"
    if damage == "rounding-limit": c["quantity"] = "2.50000000000000000000000000001"
    if damage == "identity": c["eligibility"]["instrument_id"] = "substitution"
    if damage == "signal": c["origin_ref"] = "invented"
    if damage == "short": c["side"] = "SHORT"
    if damage == "version": c["schema"] = "PAPER_COMMAND_FIXTURE_V1"
    if damage == "unsupported":
        with pytest.raises(ValueError): create_epoch_fixture(tmp_path / "never-created.sqlite", m)
        assert not (tmp_path / "never-created.sqlite").exists()
        return
    store = create_epoch_fixture(tmp_path / "fixture.sqlite", m)
    before = copy.deepcopy(store.snapshot())
    phases = []
    with pytest.raises((ValueError, KeyError)):
        store.execute(c, fault=phases.append)
    assert not phases and store.snapshot() == before
    with store.connect(readonly=True) as db:
        assert db.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0


@pytest.mark.parametrize("different_symbol", [False, True])
def test_one_open_position_refuses_scale_in_and_other_instrument(different_symbol):
    m, c = setup_case()
    other_m, other = setup_case("SPY", "ETF")
    m["account_policy"]["instruments"].update(other_m["account_policy"]["instruments"])
    m["account_policy"]["ranking_receipts"] += other_m["account_policy"]["ranking_receipts"]
    state, _ = finance.apply_event(m, finance.initial_state(m), c)
    second = other if different_symbol else copy.deepcopy(c)
    second.update(operation_id="second", expected_source_revision=1)
    with pytest.raises(ValueError, match="ONE_POSITION"):
        finance.apply_event(m, state, second)


def test_rank_order_changes_are_not_execution_authority_or_new_signal():
    m, c = setup_case(rank_order=8)
    state, _ = finance.apply_event(m, finance.initial_state(m), c)
    close = exit_command(m, c, state, "2.5")
    state, _ = finance.apply_event(m, state, close)
    revised = copy.deepcopy(c)
    revised.update(operation_id="rank-change", expected_source_revision=2, timestamp=state["last_clock"])
    revised["eligibility"]["ranking"].update(rank=1, revision=2)
    m["account_policy"]["ranking_receipts"].append(finance.digest(revised["eligibility"]["ranking"]))
    with pytest.raises(ValueError, match="Origin already"):
        finance.apply_event(m, state, revised)
    revised["manual"] = False
    with pytest.raises(ValueError, match="MANUAL_CONFIRMATION"):
        finance.apply_event(m, state, revised)


def test_cash_constraint_is_independent_of_notional_limit():
    m, c = setup_case()
    state = finance.initial_state(m)
    state["cash"] = "99"
    with pytest.raises(ValueError, match="INSUFFICIENT_CASH"):
        finance.apply_event(m, state, c)
    assert state["cash"] == "99"


@pytest.mark.parametrize("field,value", [("opening_cash", "1001"), ("fees_bps", "0"),
    ("max_positions", 2), ("max_entry_usd", "101"), ("evidence_scope", "OPERATIONAL"),
    ("ranking_max_age_seconds", True)])
def test_policy_cannot_silently_expand_accepted_offline_parameters(field, value):
    m, _ = setup_case()
    (m if field in m else m["account_policy"])[field] = value
    with pytest.raises(ValueError): finance.validate_manifest(m)


def test_unverified_symbol_refused_even_when_highly_ranked():
    m, c = setup_case()
    c["symbol"] = c["quote"]["symbol"] = "UNVERIFIED"
    c["eligibility"]["ranking"].update(symbol="UNVERIFIED", rank=1)
    m["account_policy"]["ranking_receipts"].append(finance.digest(c["eligibility"]["ranking"]))
    with pytest.raises(ValueError, match="INSTRUMENT_IDENTITY"):
        finance.apply_event(m, finance.initial_state(m), c)


def test_ranked_etf_can_follow_closed_stock_without_account_mixing(tmp_path):
    m, first = setup_case("AAPL", rank_order=7)
    other_m, second = setup_case("QQQ", "ETF", rank_order=2)
    m["account_policy"]["instruments"].update(other_m["account_policy"]["instruments"])
    m["account_policy"]["ranking_receipts"] += other_m["account_policy"]["ranking_receipts"]
    store = create_epoch_fixture(tmp_path / "sequence.sqlite", m)
    store.execute(first)
    store.execute(exit_command(m, first, store.snapshot(), "2.5"))
    second.update(expected_source_revision=2, operation_id="etf-entry", timestamp=store.snapshot()["last_clock"])
    store.execute(second)
    assert len(store.snapshot()["positions"]) == 2
    assert sum(finance.number(p["remaining"]) > 0 for p in store.snapshot()["positions"].values()) == 1


def test_exit_does_not_need_current_rank_but_requires_manual_and_fresh_price():
    m, c = setup_case()
    state, _ = finance.apply_event(m, finance.initial_state(m), c)
    command = exit_command(m, c, state, "1", elapsed=86400)
    command["manual"] = False
    with pytest.raises(ValueError): finance.apply_event(m, state, command)
    command["manual"] = True
    command["quote"]["observed_at"] -= 31
    with pytest.raises(ValueError): finance.apply_event(m, state, command)


def test_native_store_computes_canonical_transition_before_intent_without_running_native_code():
    import ast

    path = Path(__file__).parents[1] / "scripts/volume_inspector/financial_record_store.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    execute = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "execute")
    source = ast.get_source_segment(path.read_text(encoding="utf-8"), execute)
    assert source.index("apply_event(") < source.index('"intent"')
