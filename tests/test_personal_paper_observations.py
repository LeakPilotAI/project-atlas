from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
from app.adapters.hyperliquid import Ticker
from app.investment.quality_dips_paper import (
    accounting_snapshot,
    initialize_paper_account,
    open_lot,
    read_events,
)
from app.personal_paper import (
    ACCOUNT_ID,
    create_app,
    run_test_data_session,
)
from app.services.personal_hyperliquid_public_data import (
    append_public_data,
    build_public_record,
)
from app.services.personal_paper_observations import (
    FORWARD_ACCOUNT_ID,
    evaluate_public_observations,
    process_public_observations,
)
from app.services.personal_public_market_data import (
    append_market_data,
    build_yahoo_public_record,
)
from fastapi.testclient import TestClient


def _write_observations(tmp_path, now: datetime, *, include_open_candle: bool = False):
    market_path = tmp_path / "market.jsonl"
    hyperliquid_path = tmp_path / "hyperliquid.jsonl"
    daily = pd.DataFrame(
        {
            "Open": [68.0],
            "High": [72.0],
            "Low": [67.0],
            "Close": [70.0],
            "Adj Close": [70.0],
            "Volume": [10000],
        },
        index=pd.DatetimeIndex([now.astimezone(ZoneInfo("America/New_York")).date()]),
    )
    intraday = pd.DataFrame(
        {"Close": [70.0]},
        index=pd.DatetimeIndex([now - timedelta(seconds=20)]),
    )
    yahoo = build_yahoo_public_record(
        "MSFT",
        intraday,
        daily,
        request_started_at=now - timedelta(seconds=25),
        retrieved_at=now,
    )
    append_market_data(market_path, yahoo)

    started = now - timedelta(seconds=2)
    tickers = [
        Ticker(symbol=symbol, price=100.0 + index, timestamp=started.isoformat())
        for index, symbol in enumerate(("BTC", "ETH", "SOL"))
    ]
    bars = {}
    for symbol in ("BTC", "ETH", "SOL"):
        rows = []
        for offset in range(30, 0, -1):
            stamp = int((now - timedelta(days=offset)).timestamp() * 1000)
            close = 100.0 + (30 - offset)
            rows.append(
                {
                    "time": stamp,
                    "open": close - 1,
                    "high": close + 2,
                    "low": close - 2,
                    "close": close,
                    "volume": 1000.0 + close,
                    "n": 100,
                }
            )
        if include_open_candle:
            stamp = int((now - timedelta(hours=12)).timestamp() * 1000)
            rows.append(
                {
                    "time": stamp,
                    "open": 130.0,
                    "high": 132.0,
                    "low": 128.0,
                    "close": 131.0,
                    "volume": 1200.0,
                    "n": 100,
                }
            )
        bars[symbol] = rows
    hyperliquid = build_public_record(
        tickers,
        bars,
        request_started_at=started,
        retrieved_at=now,
        request_budget_remaining=8,
    )
    append_public_data(hyperliquid_path, hyperliquid)
    return market_path, hyperliquid_path


def _research(now: datetime):
    return [
        {
            "symbol": "MSFT",
            "timestamp": now.isoformat(),
            "normalization_value": {
                "conservative": 100.0,
                "base": 100.0,
                "optimistic": 100.0,
            },
            "quality_score": 95,
            "fundamentals_score": 90,
            "valuation_score": 85,
            "drawdown": {"percentile": 95},
            "evidence_quality": "HIGH",
            "thesis": "INTACT",
        }
    ]


def test_real_public_observations_are_evaluated_but_not_filled(tmp_path):
    now = datetime.now(UTC)
    market_path, hyperliquid_path = _write_observations(tmp_path, now)
    rows, _ = evaluate_public_observations(
        market_data_path=market_path,
        hyperliquid_data_path=hyperliquid_path,
        research_rows=_research(now),
        now=now,
    )

    qd = next(row for row in rows if row["strategy"] == "QUALITY_DIPS_V3")
    assert qd["strategy_result"]["patient_state"] in {
        "ACCUMULATION",
        "DEEP_VALUE",
        "GENERATIONAL",
    }
    assert qd["decision"] == "NO_TRADE"
    assert qd["paper_execution_eligible"] is False
    assert qd["source_timestamp_basis"] == "YAHOO_INTRADAY_BAR_INDEX_TIME"
    assert "YAHOO_TRADE_BAR_CLOSE_IS_NOT_AN_EXECUTABLE_QUOTE" in qd["blockers"]

    perp = [row for row in rows if row["strategy"] == "HYPERLIQUID_PERP_DISCOVERY"]
    assert {row["symbol"] for row in perp} == {"BTC", "ETH", "SOL"}
    assert all(row["closed_candle_count"] == 30 for row in perp)
    assert all(row["price_kind"] == "HISTORICAL_CLOSED_DAILY_CANDLE_CLOSE" for row in perp)
    assert all(row["paper_execution_eligible"] is False for row in perp)


def test_unclosed_hyperliquid_candles_and_stale_snapshots_cannot_drive_entries(tmp_path):
    now = datetime.now(UTC)
    market_path, hyperliquid_path = _write_observations(
        tmp_path,
        now,
        include_open_candle=True,
    )
    observations, _ = evaluate_public_observations(
        market_data_path=market_path,
        hyperliquid_data_path=hyperliquid_path,
        research_rows=_research(now),
        now=now,
    )
    assert all(
        row["closed_candle_count"] == 30
        for row in observations
        if row["strategy"] == "HYPERLIQUID_PERP_DISCOVERY"
    )

    stale, _ = evaluate_public_observations(
        market_data_path=market_path,
        hyperliquid_data_path=hyperliquid_path,
        research_rows=_research(now),
        now=now + timedelta(minutes=16),
    )
    assert all(row["paper_execution_eligible"] is False for row in stale)
    assert "YAHOO_PUBLIC_SNAPSHOT_STALE" in next(
        row["blockers"] for row in stale if row["strategy"] == "QUALITY_DIPS_V3"
    )
    assert "YAHOO_MARKET_OBSERVATION_STALE" in next(
        row["blockers"] for row in stale if row["strategy"] == "QUALITY_DIPS_V3"
    )
    assert all(
        "HYPERLIQUID_PUBLIC_SNAPSHOT_STALE" in row["blockers"]
        for row in stale
        if row["strategy"] == "HYPERLIQUID_PERP_DISCOVERY"
    )


def test_personal_paper_market_cycle_dashboard_restart_and_test_fixture(tmp_path):
    now = datetime.now(UTC)
    market_path, hyperliquid_path = _write_observations(tmp_path, now)
    forward_path = tmp_path / "forward.jsonl"
    strategy_path = tmp_path / "strategy.jsonl"
    test_path = tmp_path / "test-data.jsonl"

    cycle = process_public_observations(
        market_data_path=market_path,
        hyperliquid_data_path=hyperliquid_path,
        forward_journal_path=forward_path,
        strategy_observation_path=strategy_path,
        research_rows=_research(now),
        now=now,
    )
    assert cycle["decision_count"] == 4
    assert cycle["paper_positions_opened"] == 0
    assert cycle["broker_order_created"] is False
    retry = process_public_observations(
        market_data_path=market_path,
        hyperliquid_data_path=hyperliquid_path,
        forward_journal_path=forward_path,
        strategy_observation_path=strategy_path,
        research_rows=_research(now),
        now=now,
    )
    assert retry["strategy_observation_journal_count"] == 4
    assert len(read_events(forward_path)) == cycle["forward_account_events"]

    fixture = run_test_data_session(test_path)
    assert fixture["data_provenance"] == "TEST_DATA"
    assert fixture["entry"]["evidence_class"] == "TEST_DATA"
    assert fixture["portfolio"]["accounting"]["open_positions"] == 0

    app = create_app(
        test_path,
        market_path,
        hyperliquid_path,
        forward_journal_path=forward_path,
        strategy_observations_path=strategy_path,
    )
    with TestClient(app) as client:
        assert client.get("/api/paper/forward/portfolio").json()["accounting"][
            "data_provenance"
        ] == "FORWARD_COLLECTION"
        forward_report = client.get("/api/paper/forward/report").json()
        assert forward_report["genuine_forward_paper"] is True
        assert forward_report["current_available_cash"] == 1000.0
        assert forward_report["closed_trades"] == 0
        assert client.get("/api/strategy/observations").json()["record_count"] == 4
        assert client.get("/api/paper/trades").json()["data_provenance"] == "TEST_DATA"
        assert client.post("/api/paper/forward/trades").status_code == 405
        first_status = client.get("/api/paper/status").json()
        assert first_status["forward_paper"]["paper_positions"] == 0

    with TestClient(app) as client:
        assert client.get("/api/paper/forward/portfolio").json()["accounting"][
            "available_cash"
        ] == 1000.0
        assert client.get("/api/strategy/observations").json()["record_count"] == 4
        assert client.get("/api/paper/report").json()["data_provenance"] == "TEST_DATA"

    events = read_events(forward_path)
    assert accounting_snapshot(events, account_id=FORWARD_ACCOUNT_ID)["cash_reconciled"] is True
    assert len([row for row in events if row["event"] == "decision"]) == 1
    test_account = accounting_snapshot(read_events(test_path), account_id=ACCOUNT_ID)
    assert test_account["data_provenance"] == "TEST_DATA"


def test_forward_account_refuses_test_fixture_observation(tmp_path):
    path = tmp_path / "forward-account.jsonl"
    initialize_paper_account(
        account_id=FORWARD_ACCOUNT_ID,
        opening_cash=1000,
        fee_bps_per_side=2,
        max_open_positions=1,
        data_provenance="FORWARD_COLLECTION",
        path=path,
    )
    with pytest.raises(ValueError, match="FORWARD_COLLECTION account"):
        open_lot(
            {
                "observation_id": "test-fixture",
                "symbol": "MSFT",
                "price": 70.0,
                "evidence_class": "TEST_DATA",
            },
            level="L1",
            paper_notional_dollars=100,
            account_id=FORWARD_ACCOUNT_ID,
            fee_bps_per_side=2,
            path=path,
        )
    assert accounting_snapshot(read_events(path), account_id=FORWARD_ACCOUNT_ID)[
        "available_cash"
    ] == 1000.0
