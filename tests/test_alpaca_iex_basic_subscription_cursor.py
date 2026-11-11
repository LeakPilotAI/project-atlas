"""Nonfinancial IEX subscription resume receipts: real disk, fake network only."""
import asyncio
import json

import pytest

from scripts.observation_runtime import alpaca_iex_basic_research_batch as batch
from scripts.observation_runtime import alpaca_iex_basic_subscription_cursor as cursor
from scripts.observation_runtime.alpaca_equity_catalog import inventory_snapshot


def catalog(n=68):
    return inventory_snapshot([
        {"class": "us_equity", "symbol": f"S{i:03d}", "status": "active",
         "tradable": True, "exchange": "NASDAQ", "id": str(i)}
        for i in range(n)], captured_at="2026-11-11T09:00:00+00:00")


@pytest.fixture
def staged(monkeypatch, tmp_path):
    path = tmp_path / "iex_basic_subscription_cursor.json"
    monkeypatch.setattr(cursor, "CURSOR", path)
    monkeypatch.setattr(batch, "inspect_selected_data_only", lambda: {
        "selected_revision": 14, "trading_authorized": False,
        "provider_rights_independently_accepted": False})
    monkeypatch.setattr(batch, "catalog_snapshot", lambda: catalog())
    return path


async def fake_observer(*, scope, offset, pinned_research_symbols, seconds,
                        auth=True, extra=None, fresh=False):
    roster = batch.prepare(scope=scope, offset=offset,
                           pinned_research_symbols=pinned_research_symbols)
    diagnostics = {s: {"received": 0, "accepted": 0,
                       "rejected": 0, "fresh_callbacks": 0}
                   for s in roster["requested_symbols"]}
    if fresh:
        diagnostics[roster["requested_symbols"][0]]["received"] = 1
        diagnostics[roster["requested_symbols"][0]]["accepted"] = 1
    result = {
        "endpoint": "wss://stream.data.alpaca.markets/v2/iex",
        "feed": "IEX", "authenticated": auth, "subscribed": auth,
        "reconnects": 0, "fresh_quote_observed_during_connection": fresh,
        "per_symbol_quote_diagnostics": diagnostics,
        "quote_count": 1 if fresh else 0,
        "result": {"connection": "DISCONNECTED", "paper_startup_authorized": False,
                   "quotes": [{"bid": "SUPER_SECRET_RAW_BID"}]}}
    report = batch.sanitize(roster, result, seconds=seconds)
    if extra:
        report.update(extra)
    return report


def run(*, pins=(), seconds=12, observer=fake_observer):
    return asyncio.run(cursor.resume_one(
        scope=batch.SCOPE, pinned_research_symbols=pins, seconds=seconds,
        observer=observer))


def test_subscriptions_resume_three_nonoverlapping_batches_without_market_coverage(staged):
    results = [run() for _ in range(3)]
    assert [(r["research_offset"], r["next_subscription_research_offset_saved"])
            for r in results] == [(0, 30), (30, 60), (60, 68)]
    assert [r["research_subscription_generation"] for r in results] == [1, 2, 3]
    assert all(r["research_subscription_checkpoint_committed"] is True for r in results)
    assert all(r["cursor_durably_committed"] is False for r in results)
    assert all(r["financial_execution_cursor_committed"] is False for r in results)
    assert all(r["acknowledged_subscriptions_are_fresh_quotes"] is False for r in results)
    assert all(r["quote_messages_received"] == 0 for r in results)
    assert all("quotes" not in r and "SUPER_SECRET" not in str(r) for r in results)
    state = cursor.read_cursor()
    assert state["generation"] == 3
    assert state["next_research_offset"] == 68
    assert state["total_acknowledged_subscription_symbols"] == 68
    assert state["financial_source_accepted"] is False
    assert state["raw_prices_stored"] is False
    assert state["paper_start_authorized"] is False
    assert state["live_money_authorized"] is False
    with pytest.raises(ValueError, match="CYCLE_COMPLETE"):
        run()


def test_pinned_research_monitor_remains_on_every_batch(staged):
    a = run(pins=["S000"])
    b = run(pins=["S000"])
    assert a["requested_symbols_count"] == b["requested_symbols_count"] == 30
    assert (a["research_offset"], a["next_subscription_research_offset_saved"]) == (0, 29)
    assert (b["research_offset"], b["next_subscription_research_offset_saved"]) == (29, 58)
    assert cursor.read_cursor()["total_acknowledged_subscription_symbols"] == 60


def test_fresh_quote_changes_counts_but_never_financial_authority(staged):
    async def observed(**kwargs):
        return await fake_observer(**kwargs, fresh=True)
    r = run(observer=observed)
    assert r["quote_messages_accepted"] == 1
    assert r["current_qualified_market_source"] is False
    assert r["paper_start_authorized"] is False
    assert cursor.read_cursor()["last_quote_messages_accepted"] == 1
    assert "SUPER_SECRET_RAW_BID" not in staged.read_text()


@pytest.mark.parametrize("change", [
    {"orders_created": 1},
    {"paper_start_authorized": True},
    {"raw_quotes_or_prices_published": True},
    {"current_qualified_market_source": True},
    {"cursor_durably_committed": True},
    {"financial_position_owner_verified": True},
    {"independent_provider_contract_rights_accepted": True},
    {"quotes": [{"bid": "UNSAFE"}]},
    {"next_research_offset_uncommitted": 190},
    {"quote_messages_received": True},
])
def test_forged_or_price_bearing_report_cannot_advance(staged, change):
    async def observed(**kwargs):
        return await fake_observer(**kwargs, extra=change)
    with pytest.raises(ValueError, match="ONLY_EXACT_NONFINANCIAL_ACK"):
        run(observer=observed)
    assert cursor.read_cursor() is None
    assert not staged.with_suffix(".lock").exists()


def test_failed_auth_does_not_save_cursor(staged):
    async def observed(**kwargs):
        return await fake_observer(**kwargs, auth=False)
    with pytest.raises(ValueError, match="ONLY_EXACT_NONFINANCIAL_ACK"):
        run(observer=observed)
    assert cursor.read_cursor() is None


def test_provider_exception_does_not_advance_or_leave_lock(staged):
    async def observed(**kwargs):
        raise RuntimeError("OFFLINE_FAKE_PROVIDER_FAILURE")
    with pytest.raises(RuntimeError):
        run(observer=observed)
    assert cursor.read_cursor() is None
    assert not staged.with_suffix(".lock").exists()


@pytest.mark.parametrize("bad", [0, 4, 21, True, "12"])
def test_invalid_duration_refused_before_observation(staged, bad):
    async def observed(**kwargs):
        pytest.fail("must not reach network")
    with pytest.raises(ValueError, match="EXPLICIT_BOUNDED"):
        run(seconds=bad, observer=observed)
    assert cursor.read_cursor() is None


def test_existing_stale_lock_blocks_double_writers(staged):
    lock = staged.with_suffix(".lock")
    lock.write_text("stale", encoding="ascii")
    with pytest.raises(ValueError, match="STALE_LOCK"):
        run()
    assert lock.exists()
    assert cursor.read_cursor() is None


def test_saved_digest_corruption_blocks_resume(staged):
    run()
    state = json.loads(staged.read_text(encoding="ascii"))
    state["next_research_offset"] += 1
    staged.write_text(json.dumps(state), encoding="ascii")
    async def observed(**kwargs):
        pytest.fail("no network on corrupted checkpoint")
    with pytest.raises(ValueError, match="DIGEST_REFUSED"):
        run(observer=observed)


def test_changed_catalog_blocks_resume_before_network(staged, monkeypatch):
    run()
    monkeypatch.setattr(batch, "catalog_snapshot", lambda: catalog(69))
    async def observed(**kwargs):
        pytest.fail("changed catalogue must not launch socket")
    with pytest.raises(ValueError, match="CATALOG_OR_PINNED"):
        run(observer=observed)


def test_changed_pins_block_resume_before_network(staged):
    run()
    async def observed(**kwargs):
        pytest.fail("changed pins must not launch socket")
    with pytest.raises(ValueError, match="CATALOG_OR_PINNED"):
        run(pins=["S000"], observer=observed)


def test_unaccepted_selected_release_blocks_resume_before_network(staged, monkeypatch):
    monkeypatch.setattr(batch, "inspect_selected_data_only", lambda: {
        "selected_revision": 14, "trading_authorized": True,
        "provider_rights_independently_accepted": False})
    async def observed(**kwargs):
        pytest.fail("no socket allowed")
    with pytest.raises(ValueError, match="EXACT_SELECTED"):
        run(observer=observed)
    assert cursor.read_cursor() is None


def test_atomic_replace_failure_keeps_old_cursor_and_cleans_temp(staged, monkeypatch):
    run()
    previous = staged.read_bytes()
    def broken_replace(*args):
        raise PermissionError("TEST_ONLY_ATOMIC_REPLACE_REFUSED")
    monkeypatch.setattr(cursor.os, "replace", broken_replace)
    with pytest.raises(PermissionError):
        run()
    assert staged.read_bytes() == previous
    assert sorted(p.name for p in staged.parent.iterdir()) == [staged.name]


def test_offline_inspect_displays_only_subscription_cursor_without_provider(staged, monkeypatch, capsys):
    assert cursor.main(["--inspect"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["saved_generation"] == 0
    assert summary["next_research_offset"] == 0
    assert summary["data_provider_called"] is False
    run()
    assert cursor.main(["--inspect"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["saved_generation"] == 1
    assert summary["next_research_offset"] == 30
    assert summary["paper_start_authorized"] is False
    assert cursor.main(["--execute-data-only"]) == 2
    refused = json.loads(capsys.readouterr().out)
    assert refused["status"] == "NONFINANCIAL_SURVEY_REFUSED"


def test_finite_research_cursor_is_not_native_writer_or_market_source(staged):
    run()
    data = staged.read_bytes()
    assert b"broker" not in data and b"quotes" not in data
    assert b"provider_rights_accepted" not in data
    assert b"financial_source_accepted" in data
    assert b'"financial_source_accepted":false' in data
    assert b'"raw_prices_stored":false' in data


def test_selected_release_changes_during_observation_refuses_checkpoint(staged, monkeypatch):
    async def observed(**kwargs):
        report = await fake_observer(**kwargs)
        monkeypatch.setattr(batch, "inspect_selected_data_only", lambda: {
            "selected_revision": 14, "trading_authorized": True,
            "provider_rights_independently_accepted": False})
        return report
    with pytest.raises(ValueError, match="EXACT_SELECTED"):
        run(observer=observed)
    assert cursor.read_cursor() is None


def test_catalog_changes_during_observation_refuses_checkpoint(staged, monkeypatch):
    async def observed(**kwargs):
        report = await fake_observer(**kwargs)
        monkeypatch.setattr(batch, "catalog_snapshot", lambda: catalog(69))
        return report
    with pytest.raises(ValueError, match="CHANGED_DURING_SESSION"):
        run(observer=observed)
    assert cursor.read_cursor() is None


def test_failure_on_second_connection_preserves_first_valid_checkpoint(staged):
    run()
    before = staged.read_bytes()
    async def observed(**kwargs):
        return await fake_observer(**kwargs, auth=False)
    with pytest.raises(ValueError, match="ONLY_EXACT_NONFINANCIAL_ACK"):
        run(observer=observed)
    assert staged.read_bytes() == before
    assert not staged.with_suffix(".lock").exists()


@pytest.mark.parametrize("invalid", [
    {"status": "OPERATIONAL_FINANCIAL_SOURCE"},
    {"selected_native_release": "R16"},
    {"one_websocket_connection_seconds": 200},
    {"pinned_research_symbols_count": 500},
    {"orders_created": False},
    {"quote_messages_rejected": True},
    {"quote_messages_rejected": 1},
    {"symbols_with_accepted_quote": 900},
    {"fresh_quotes_seen_during_connection": 1},
])
def test_additional_counter_or_scope_spoof_is_refused(staged, invalid):
    async def observed(**kwargs):
        return await fake_observer(**kwargs, extra=invalid)
    with pytest.raises(ValueError, match="ONLY_EXACT_NONFINANCIAL_ACK"):
        run(observer=observed)
    assert cursor.read_cursor() is None
