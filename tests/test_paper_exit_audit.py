import hashlib
import json
import sqlite3

import pytest
from app.services.daily_paper_liquidation import append_partial_fixture, liquidate
from app.services.paper_exit_audit import audit_fixture_exits
from test_durable_partial_shutdown import fixture


@pytest.mark.parametrize("damage", [None, "net", "quantity", "missing", "gross", "fee"])
def test_independent_remaining_exit_audit(tmp_path, damage):
    path, fill = fixture(tmp_path)
    append_partial_fixture(path, "t", fill)
    liquidate(path, "s", {"T": {"price": "104", "observed_at": 3, "verified": True, "source_id": "fixture"}}, now=3, max_age=1)
    if damage:
        with sqlite3.connect(path) as db:
            if damage == "missing":
                db.execute("DELETE FROM partial_fills")
            else:
                row = json.loads(db.execute("SELECT body FROM exits").fetchone()[0])
                key = {"net": "net", "quantity": "shutdown_quantity", "gross": "gross", "fee": "exit_fee"}[damage]
                row["currency_accounting"][key] = "900"
                db.execute("UPDATE exits SET body=?", (json.dumps(row),))
        with pytest.raises(ValueError):
            audit_fixture_exits(path)
    else:
        assert audit_fixture_exits(path)["reconciled"]


@pytest.mark.parametrize("damage", ["missing", "changed", "extra"])
def test_trusted_fixture_inventory_detects_source_omission(tmp_path, damage):
    path, _ = fixture(tmp_path)
    with sqlite3.connect(path) as db:
        rows = db.execute("SELECT id,body FROM positions").fetchall()
        expected = {ident: hashlib.sha256(json.dumps(json.loads(body), sort_keys=True).encode()).hexdigest()
                    for ident, body in rows}
        if damage == "missing":
            db.execute("DELETE FROM positions")
        elif damage == "changed":
            p = json.loads(rows[0][1])
            p["quantity"] = "9"
            db.execute("UPDATE positions SET body=?", (json.dumps(p),))
        else:
            db.execute("INSERT INTO positions VALUES('other',?)", (rows[0][1],))
    with pytest.raises(ValueError, match="original position"):
        audit_fixture_exits(path, expected_positions=expected)
