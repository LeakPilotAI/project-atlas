import hashlib
import json
import sqlite3

import pytest
from app.services.paper_bound_daily_report import publish_inventory_bound_fixture
from test_bound_daily_report import setup
from test_durable_partial_shutdown import fixture


def inventory(path, version=1):
    with sqlite3.connect(path) as db:
        sources = {table: hashlib.sha256(json.dumps(db.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall(), sort_keys=True).encode()).hexdigest()
                   for table in ("positions", "partial_fills", "exits", "cash_evidence")}
    return {"identity": "explicit-fixture-custodian", "version": version, "sources": sources}


@pytest.mark.parametrize("damage", [None, "missing", "changed", "corrupt", "rollback"])
def test_inventory_bound_report_refusal_and_replay(tmp_path, damage):
    path, _ = fixture(tmp_path)
    setup(path)
    claim = inventory(path, 2)
    def publish(value):
        return publish_inventory_bound_fixture(path, day="1970-01-01", timezone="UTC", currency="USD", inventory=value)
    first = publish(claim)
    assert first["independently_authenticated"] is False
    if damage is None:
        assert publish(claim) == first
        return
    if damage == "missing":
        claim = None
    elif damage == "changed":
        with sqlite3.connect(path) as db:
            db.execute("DELETE FROM positions")
    elif damage == "corrupt":
        claim["sources"]["positions"] = "bad"
    else:
        claim["version"] = 1
    with pytest.raises(ValueError):
        publish(claim)
