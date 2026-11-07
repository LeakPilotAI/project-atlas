import copy
import sqlite3
from decimal import Decimal

import pytest
from app.services.paper_epoch_fixture import create_epoch_fixture
from app.services.paper_portfolio_fixture import (
    account_summary_fixture,
    portfolio_payload_fixture,
    render_portfolio_fixture,
)
from app.services.paper_strategy_fixture import exit_command
from test_paper_epoch_fixture import STAMP, entry, manifest, quote
from test_q7_paper_workflows import q7_native


def test_separate_accounts_deterministic_payload_and_readonly_presentation(tmp_path):
    a = create_epoch_fixture(tmp_path / "a.sqlite", manifest("quality<script>", "QUALITY_DIPS"))
    b = create_epoch_fixture(tmp_path / "b.sqlite", manifest("perps"))
    rows = [account_summary_fixture(s, now=STAMP, max_age=30) for s in (a, b)]
    payload = portfolio_payload_fixture(rows)
    assert portfolio_payload_fixture(list(reversed(rows))) == payload
    assert payload["portfolio_totals"] is None and payload["consolidation"] == "NOT_AUTHORIZED"
    html = render_portfolio_fixture(payload)
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "No combined equity" in html
    with a.connect(readonly=True) as db, pytest.raises(sqlite3.OperationalError):
        db.execute("DELETE FROM inception")


@pytest.mark.parametrize("bad", ["duplicate", "same-epoch", "schema", "authority", "equity", "nonfinite", "missing-cash", "unknown-cash"])
def test_malformed_presentation_contract_fails_closed(tmp_path, bad):
    s = create_epoch_fixture(tmp_path / "a.sqlite", manifest())
    row = account_summary_fixture(s, now=STAMP, max_age=30)
    rows = [copy.deepcopy(row)]
    if bad == "duplicate": rows.append(row)
    if bad == "same-epoch": rows.append({**row, "strategy": "QUALITY_DIPS"})
    if bad == "schema": rows[0]["schema"] = "OLD"
    if bad == "authority": rows[0]["startup_authorized"] = True
    if bad == "equity": rows[0]["total_equity"] = "1000"
    if bad == "nonfinite": rows[0]["reconciled_cash"] = "NaN"
    if bad == "missing-cash": rows[0]["reconciled_cash"] = None
    if bad == "unknown-cash": rows[0]["state"] = "UNKNOWN"
    with pytest.raises(ValueError): portfolio_payload_fixture(rows)


def test_unknown_and_stale_are_not_hidden_as_current_complete(tmp_path):
    s = create_epoch_fixture(tmp_path / "a.sqlite", manifest())
    stale = account_summary_fixture(s, now=STAMP + 31, max_age=30)
    assert stale["state"] == "INCOMPLETE" and stale["freshness"]["status"] == "STALE"
    assert stale["freshness"]["basis"] == "FINANCIAL_EVENT_NOT_MARKET_QUOTE"
    assert stale["total_equity"] is None and "market_data_freshness" in stale["unavailable_metrics"]
    future = account_summary_fixture(s, now=STAMP - 1, max_age=30)
    assert future["state"] == "UNKNOWN" and future["reconciled_cash"] is None
    with s.connect() as db: db.execute("UPDATE inception SET body='{}'")
    unknown = account_summary_fixture(s, now=STAMP, max_age=30)
    assert unknown["state"] == "UNKNOWN" and unknown["remaining_positions"] is None
    assert "Unavailable" in render_portfolio_fixture(portfolio_payload_fixture([unknown]))


def test_native_verification_cannot_be_omitted(tmp_path):
    store, bridge, _, _ = q7_native(tmp_path)
    bridge.apply(entry(store))
    assert account_summary_fixture(store, now=STAMP, max_age=30)["state"] == "UNKNOWN"
    verified = account_summary_fixture(store, reader=bridge, now=STAMP, max_age=30)
    assert verified["state"] == "INCOMPLETE" and len(verified["remaining_positions"]) == 1
    assert Decimal(verified["reconciled_cash"]) == 1000


def test_independent_financial_audit_rejects_inconsistent_reader(tmp_path):
    store = create_epoch_fixture(tmp_path / "a.sqlite", manifest())
    pos = store.execute(entry(store))["position_id"]
    store.execute(exit_command(store, operation_id="close", position_id=pos, quantity="0.5",
                               quote=quote("104"), timestamp=STAMP, manual=True))
    class ForgedReader:
        def snapshot(self):
            state = store.snapshot()
            state["cash"] = "9999"
            return state
    summary = account_summary_fixture(store, reader=ForgedReader(), now=STAMP, max_age=30)
    assert summary["state"] == "UNKNOWN" and summary["reconciled_cash"] is None


def test_empty_summary_is_explicit_and_no_totals():
    payload = portfolio_payload_fixture([])
    assert payload["accounts"] == [] and payload["portfolio_totals"] is None
    assert "<tbody></tbody>" in render_portfolio_fixture(payload)


@pytest.mark.parametrize("bad", ["net", "freshness", "stale-complete", "extra-field"])
def test_summary_consistency_not_just_field_presence(tmp_path, bad):
    store = create_epoch_fixture(tmp_path / "a.sqlite", manifest())
    row = account_summary_fixture(store, now=STAMP, max_age=30)
    if bad == "net": row["realized_net"] = "100"
    if bad == "freshness": row["freshness"]["age_seconds"] = 5
    if bad == "stale-complete":
        row["max_event_age_seconds"] = 0
        row["observed_at"] += 1
        row["freshness"].update(age_seconds=1, status="STALE")
    if bad == "extra-field": row["approved"] = True
    with pytest.raises(ValueError): portfolio_payload_fixture([row])


def test_replacement_and_clearing_never_retain_old_account_rows(tmp_path):
    a = create_epoch_fixture(tmp_path / "a.sqlite", manifest("old"))
    b = create_epoch_fixture(tmp_path / "b.sqlite", manifest("new"))
    before = portfolio_payload_fixture([account_summary_fixture(a, now=STAMP, max_age=30)])
    after = portfolio_payload_fixture([account_summary_fixture(b, now=STAMP, max_age=30)])
    assert before["accounts"][0]["epoch"] == "old" and after["accounts"][0]["epoch"] == "new"
    assert "old" not in render_portfolio_fixture(after)
    assert portfolio_payload_fixture([])["accounts"] == []
