import hashlib
import json

import pytest
from app.services.hyperliquid_paper_handoff import manual_journal_fixture_consistency
from app.trading_core.perp_manual_state_store import ManualPerpStateStore
from test_hyperliquid_paper_handoff import actual_journal, handoff, open_actual
from test_hyperliquid_store_integration import manual_plan


@pytest.mark.parametrize("damage", [None, "missing", "duplicate", "symbol", "status", "version", "pin", "unknown"])
def test_actual_native_snapshot_journal_revision_consistency(tmp_path, damage):
    module, journal = actual_journal(tmp_path)
    ident = open_actual(journal)
    state = ManualPerpStateStore(tmp_path / "manual.json")
    plan = {**manual_plan("BTC", "LONG"), "fixture_journal_trade_id": ident}
    state.save(plans=[plan], setup_history=[])
    assert state.load()["plans"] == [plan]
    raw = state.path.read_bytes()
    data = json.loads(raw)
    if damage == "missing": data["plans"] = []
    if damage == "duplicate": data["plans"].append(plan)
    if damage == "symbol": data["plans"][0]["symbol"] = "ETH"
    if damage == "status": data["plans"][0]["status"] = "CLOSED"
    if damage == "version": data["version"] = 2
    if damage == "unknown": data["plans"][0]["fixture_journal_trade_id"] = "unbound"
    if damage: raw = (json.dumps(data) + "\n").encode()
    digest = "0" * 64 if damage == "pin" else hashlib.sha256(raw).hexdigest()
    if damage:
        with pytest.raises(ValueError):
            manual_journal_fixture_consistency(raw, expected_sha256=digest, journal=handoff(module.JOURNAL_PATH.read_bytes()))
    else:
        receipt = manual_journal_fixture_consistency(raw, expected_sha256=digest, journal=handoff(module.JOURNAL_PATH.read_bytes()))
        assert receipt["entered_ids"] == [ident] and receipt["native_positions_flat"] is False
        assert receipt["shutdown_authorized"] is receipt["source_completeness_independently_proven"] is False
