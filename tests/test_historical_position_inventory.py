import sqlite3

import pytest
from app.services.daily_paper_liquidation import append_partial_fixture, liquidate
from app.services.paper_historical_inventory import historical_fixture_inventory
from test_durable_partial_shutdown import fixture


def test_partial_and_final_historical_boundaries(tmp_path):
    path, fill = fixture(tmp_path)
    fill["timestamp"] = 10
    append_partial_fixture(path, "t", fill)
    liquidate(path, "s", {"T": {"price": "104", "observed_at": 20, "verified": True, "source_id": "fixture"}}, now=20, max_age=1)
    assert historical_fixture_inventory(path, cutoff=1)["positions"] == []
    assert historical_fixture_inventory(path, cutoff=10)["positions"][0]["remaining_quantity"] == "1"
    assert historical_fixture_inventory(path, cutoff=20)["positions"][0]["remaining_quantity"] == "0.75"
    assert historical_fixture_inventory(path, cutoff=21)["unresolved"] == []
    assert historical_fixture_inventory(path, cutoff=20)["historical_availability_authenticated"] is False


def test_missing_original_clock_refuses_historical_claim(tmp_path):
    import json
    path, _ = fixture(tmp_path)
    with sqlite3.connect(path) as db:
        p = json.loads(db.execute("SELECT body FROM positions").fetchone()[0])
        p.pop("opened_at")
        db.execute("UPDATE positions SET body=?", (json.dumps(p),))
    with pytest.raises(ValueError, match="timestamp"):
        historical_fixture_inventory(path, cutoff=100)
