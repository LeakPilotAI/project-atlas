"""Late evidence never invents a settlement or silently restates old cash."""
import copy

import pytest
from app.services.paper_epoch_fixture import create_epoch_fixture
from app.services.paper_financial_replay import digest
from test_perp_financial_v2 import audit, entry, funding, manifest


def recovery(store, posted=90000, at=7200):
    c = funding(store, at=at)
    c.update(schema="PAPER_PERP_FUNDING_RECOVERY_V1", timestamp=posted)
    state = store.snapshot()
    core = {k: v for k, v in state.items() if k not in {"epoch", "strategy", "report_state", "equity", "pending_projections", "startup_authorized", "shutdown_authorized"}}
    c["recovery"] = {"authority_ref": "SYNTHETIC_RECOVERY_NOT_OPERATIONAL", "state_digest": digest(core),
                     "evidence_digest": digest(c["evidence"]), "quantity": "0.5", "accepted_at": posted}
    return c


@pytest.mark.parametrize("damage", [None, "quantity", "state", "rate", "authority-absent", "clock"])
def test_late_funding_requires_exact_preexisting_position_cut(damage, tmp_path):
    st = create_epoch_fixture(tmp_path / "perp.db", manifest())
    st.execute(entry())
    c = recovery(st)
    if damage == "quantity": c["recovery"]["quantity"] = "1"
    elif damage == "state": c["recovery"]["state_digest"] = "old-cut"
    elif damage == "rate": c["evidence"]["rate"] = "0.02"
    elif damage == "authority-absent": c["recovery"]["authority_ref"] = ""
    elif damage == "clock": c["recovery"]["accepted_at"] -= 1
    before = copy.deepcopy(st.snapshot())
    if damage:
        with pytest.raises(ValueError): st.execute(c)
        assert st.snapshot() == before
    else:
        receipt = st.execute(c)
        assert st.execute(c) == receipt
        audit(st)


def test_late_recovery_report_keeps_settlement_and_posting_days_distinct(tmp_path):
    from app.services.paper_daily_report import build_daily_report
    from app.services.paper_financial_replay import event_stream_record
    st = create_epoch_fixture(tmp_path / "perp.db", manifest())
    st.execute(entry())
    st.execute(recovery(st))
    with st.connect(readonly=True) as db:
        rows = [event_stream_record(*r) for r in db.execute("SELECT * FROM events ORDER BY revision")]
    scope = {"schema": "FS3_REPORT_SCOPE_V1", "account_id": "synthetic", "epoch": manifest()["epoch"],
             "policy_digest": digest(manifest()), "timezone": "UTC"}
    pin = {"epoch": manifest()["epoch"], "entries": ["synthetic"] * len(rows), "root": [1, 2, 3], "inception": "synthetic"}
    for day in ("1970-01-01", "1970-01-02"):
        r = build_daily_report(scope, manifest(), pin, rows, day, 172800)
        assert r["status"] == "INCOMPLETE" and "RECOVERY_RESTATEMENT_REQUIRED" in r["reasons"]
        assert r["funding_postings"][0]["settlement_at"] == 7200
        assert r["funding_postings"][0]["posted_at"] == 90000


def test_versioned_restatement_separates_historical_cash_from_known_funding_accrual(tmp_path):
    from decimal import Decimal

    from app.services.paper_daily_report import audit_daily_report, build_daily_report
    from app.services.paper_financial_replay import (
        event_stream_record,
        replay_verified_events,
    )
    st = create_epoch_fixture(tmp_path / "perp.db", manifest())
    st.execute(entry())
    scope = {"schema": "FS3_PERP_REPORT_SCOPE_V2", "account_id": "synthetic", "epoch": manifest()["epoch"],
             "policy_digest": digest(manifest()), "timezone": "UTC", "funding_reporting_policy": "POSTED_CASH_AND_SETTLEMENT_ACCRUAL_V1"}
    def source():
        with st.connect(readonly=True) as db:
            rows = [event_stream_record(*r) for r in db.execute("SELECT * FROM events ORDER BY revision")]
        return rows, {"epoch": manifest()["epoch"], "entries": ["synthetic"] * len(rows), "root": [1, 2, 3], "inception": "synthetic"}
    rows, pin = source()
    original = build_daily_report(scope, manifest(), pin, rows, "1970-01-01", 86400)
    original_copy = copy.deepcopy(original)
    assert original["status"] == "INCOMPLETE"
    for hour in range(7200, 86401, 3600): st.execute(recovery(st, at=hour))
    rows, pin = source()
    updated = build_daily_report(scope, manifest(), pin, rows, "1970-01-01", 172800)
    assert updated["status"] == "COMPLETE" and updated["report_version"] == 4
    assert Decimal(updated["cash"]["closing"]) == Decimal("999.98")
    assert Decimal(updated["realized"]["funding"]) == 0
    assert Decimal(updated["funding_accrual"]["settled_in_period"]) == Decimal("-1.1")
    assert sum(Decimal(v) for v in updated["funding_accrual"]["unposted_at_cutoff"].values()) == Decimal("-1.1")
    assert updated["lifecycle_status"] == "NOT_EVALUATED" and updated["valuation"] is None
    assert original == original_copy
    updated["funding_accrual"]["settled_in_period"] = "0"
    with pytest.raises(ValueError): audit_daily_report(updated, scope, manifest(), pin, rows, replay_verified_events(manifest(), rows)[0])
