"""Authenticated interfaces are separate; these inputs are explicitly synthetic."""
from decimal import Decimal

import pytest
from app.services.paper_epoch_fixture import create_epoch_fixture
from test_perp_financial_v2 import audit, entry, exit_command, manifest


def maker():
    c = entry()
    c.update(schema="PAPER_PERP_MAKER_FILL_V1", liquidity="MAKER")
    c["evidence"]["maker_execution"] = {"schema": "SIMULATED_MAKER_QUEUE_FILL_V1", "order_id": c["origin_ref"],
        "limit_price": "95", "rested_at": 3599, "queue_ahead": "1", "traded_quantity": "10", "trade_price": "94",
        "trade_side": "SELL", "trade_at": 3601, "source_ref": "synthetic-trade-1", "requested_quantity": "0.5",
        "filled_quantity": "0.5", "cancelled_quantity": "0"}
    return c


def liquidation(store):
    c = exit_command(store, timestamp=3603, price="49")
    c["schema"] = "PAPER_PERP_LIQUIDATION_V1"
    c["evidence"]["mark"] = "50"
    c["evidence"]["liquidation"] = {"schema": "SIMULATED_BOOK_LIQUIDATION_V1", "source_cut": "synthetic-meta",
        "execution_ref": "synthetic-liq-1", "trigger_mark": "50", "maintenance": "1.25", "equity": "0",
        "quantity": "0.5", "fee_bps": "50", "fee_schedule_id": "synthetic-liq-fees", "action": "FULL_BOOK_CLOSE"}
    return c


def test_maker_fees_quote_trade_queue_and_margin_are_reconciled(tmp_path):
    st = create_epoch_fixture(tmp_path / "perp.db", manifest())
    receipt = st.execute(maker())
    assert st.execute(maker()) == receipt
    assert Decimal(st.snapshot()["fees"]) == Decimal("0.00475")
    assert Decimal(st.snapshot()["reserved_margin"]) == 25
    st.execute(exit_command(st))
    assert Decimal(st.snapshot()["cash"]) == Decimal("1003.46535")
    audit(st)


@pytest.mark.parametrize("damage", ["queue", "trade-side", "trade-price", "rest", "cancel"])
def test_maker_queue_or_trade_conflicts_refuse(damage, tmp_path):
    st = create_epoch_fixture(tmp_path / "perp.db", manifest())
    c = maker()
    proof = c["evidence"]["maker_execution"]
    if damage == "queue": proof["queue_ahead"] = "10"
    elif damage == "trade-side": proof["trade_side"] = "BUY"
    elif damage == "trade-price": proof["trade_price"] = "96"
    elif damage == "rest": proof["rested_at"] = 3602
    else: proof["cancelled_quantity"] = "1"
    with pytest.raises(ValueError): st.execute(c)
    assert st.snapshot()["revision"] == 0


def test_book_liquidation_requires_trigger_and_accounts_extra_fee(tmp_path):
    st = create_epoch_fixture(tmp_path / "perp.db", manifest())
    st.execute(entry())
    c = liquidation(st)
    st.execute(c)
    assert Decimal(st.snapshot()["liquidation_fees"]) == Decimal("0.1225")
    assert Decimal(st.snapshot()["reserved_margin"]) == 0
    assert Decimal(st.snapshot()["cash"]) == Decimal("974.34770")
    audit(st)
    from app.services.paper_daily_report import build_daily_report
    from app.services.paper_financial_replay import digest, event_stream_record
    with st.connect(readonly=True) as db:
        rows = [event_stream_record(*r) for r in db.execute("SELECT * FROM events ORDER BY revision")]
    scope = {"schema": "FS3_REPORT_SCOPE_V1", "account_id": "synthetic", "epoch": manifest()["epoch"],
             "policy_digest": digest(manifest()), "timezone": "UTC"}
    pin = {"epoch": manifest()["epoch"], "entries": ["synthetic"] * len(rows), "root": [1, 2, 3], "inception": "synthetic"}
    report = build_daily_report(scope, manifest(), pin, rows, "1970-01-01", 86400)
    assert report["report_version"] == 5 and report["status"] == "COMPLETE"
    assert Decimal(report["realized"]["liquidation_fees"]) == Decimal("0.1225")


@pytest.mark.parametrize("damage", ["equity", "maintenance", "mark", "quantity", "backstop"])
def test_liquidation_with_incomplete_or_contradictory_evidence_refuses(damage, tmp_path):
    st = create_epoch_fixture(tmp_path / "perp.db", manifest())
    st.execute(entry())
    c = liquidation(st)
    proof = c["evidence"]["liquidation"]
    if damage == "equity": proof["equity"] = "1"
    elif damage == "maintenance": proof["maintenance"] = "10"
    elif damage == "mark": proof["trigger_mark"] = "49"
    elif damage == "quantity": proof["quantity"] = "1"
    else: proof["action"] = "BACKSTOP"
    with pytest.raises(ValueError): st.execute(c)
    assert st.snapshot()["revision"] == 1
