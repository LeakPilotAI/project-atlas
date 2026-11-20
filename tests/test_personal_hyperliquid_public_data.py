from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from app.adapters import hyperliquid_gate_registry
from app.adapters.hyperliquid import HyperliquidAdapter, Ticker
from app.adapters.hyperliquid_request_gate import (
    HyperliquidRequestGate,
    RequestGateRefused,
)
from app.personal_paper import create_app, main
from app.services import personal_hyperliquid_public_data
from app.services.personal_hyperliquid_public_data import (
    DAILY_CANDLE_LOOKBACK,
    HyperliquidPublicDataError,
    append_public_data,
    build_public_record,
    fetch_public_record,
    initialize_public_data_budget,
    install_public_data_budget,
    public_data_read_model,
    read_public_data,
    require_manual_refresh_spacing,
    select_perp_symbols,
)
from fastapi.testclient import TestClient


def _observations(now: datetime | None = None):
    retrieved = now or datetime.now(UTC)
    started = retrieved - timedelta(seconds=2)
    tickers = [
        Ticker(symbol=symbol, price=100.0 + index, timestamp=started.isoformat())
        for index, symbol in enumerate(("BTC", "ETH", "SOL"))
    ]
    stamp = int((retrieved - timedelta(days=2)).timestamp() * 1000)
    candles = {
        symbol: [
            {
                "time": stamp,
                "open": 90.0,
                "high": 105.0,
                "low": 88.0,
                "close": 100.0,
                "volume": 12.0,
                "n": 20,
            },
            {
                "time": stamp + 86_400_000,
                "open": 100.0,
                "high": 110.0,
                "low": 95.0,
                "close": 105.0,
                "volume": 15.0,
                "n": 25,
            },
        ]
        for symbol in ("BTC", "ETH", "SOL")
    }
    return started, retrieved, tickers, candles


def _record(now: datetime | None = None):
    started, retrieved, tickers, candles = _observations(now)
    return build_public_record(
        tickers,
        candles,
        request_started_at=started,
        retrieved_at=retrieved,
        request_budget_remaining=8,
    )


def _gate(path):
    return HyperliquidRequestGate(
        path,
        rights_approved=True,
        budget_approved=True,
        max_attempts=12,
    )


def test_http_only_connect_refuses_without_gate_before_client_or_websocket(monkeypatch):
    adapter = HyperliquidAdapter()

    def denied():
        raise RequestGateRefused("no public-data gate")

    monkeypatch.setattr(hyperliquid_gate_registry, "require_gate", denied)
    with pytest.raises(RequestGateRefused, match="no public-data gate"):
        asyncio.run(adapter.connect_http_only())

    assert adapter._client is None
    assert adapter._ws_task is None
    assert adapter._ws_running is False


def test_http_only_connect_creates_no_websocket_worker(monkeypatch):
    adapter = HyperliquidAdapter()
    gate = object()
    monkeypatch.setattr(hyperliquid_gate_registry, "require_gate", lambda: gate)

    asyncio.run(adapter.connect_http_only())
    try:
        assert adapter._connected is True
        assert adapter._client is not None
        assert adapter._ws_task is None
        assert adapter._ws_running is False
    finally:
        asyncio.run(adapter.close())


def test_budget_initialization_is_bounded_durable_and_never_resets(tmp_path, monkeypatch):
    path = tmp_path / "hyperliquid_budget.sqlite3"
    installed = []
    monkeypatch.setattr(personal_hyperliquid_public_data, "install_gate", installed.append)

    assert initialize_public_data_budget(path) == 12
    gate = install_public_data_budget(path)
    assert installed == [gate]
    assert gate.remaining() == 12
    gate.consume_before_attempt("HTTP")
    assert initialize_public_data_budget(path) == 11
    reopened = HyperliquidRequestGate(
        path,
        rights_approved=True,
        budget_approved=True,
        max_attempts=12,
    )
    assert reopened.remaining() == 11

    with pytest.raises(RequestGateRefused):
        HyperliquidRequestGate(
            path,
            rights_approved=True,
            budget_approved=True,
            max_attempts=13,
        )


def test_hyperliquid_record_labels_public_marks_and_non_authority():
    record = _record()

    assert record["refresh_status"] == "COMPLETE"
    assert record["data_provenance"] == "PUBLIC_PROVIDER_DATA"
    assert set(record["current_marks"]) == {"BTC", "ETH", "SOL"}
    assert all(mark["provider_timestamp_available"] is False for mark in record["current_marks"].values())
    assert all(mark["price_kind"] == "MARK_PRICE" for mark in record["current_marks"].values())
    assert all(len(record["daily_bars"][symbol]) == 2 for symbol in ("BTC", "ETH", "SOL"))
    assert record["websocket_started"] is False
    assert record["private_account_accessed"] is False
    assert record["order_endpoint_used"] is False
    assert record["paper_entry_authorized"] is False
    assert record["operational_acceptance"] is False


def test_perpetual_discovery_keeps_core_and_adds_top_liquid_markets_with_coverage(tmp_path):
    started, retrieved, tickers, core_candles = _observations()
    extra_symbols = [f"ASSET{index}" for index in range(1, 10)]
    extras = [
        Ticker(
            symbol=symbol,
            price=200.0 + index,
            volume_24h=float(100 - index),
            timestamp=started.isoformat(),
        )
        for index, symbol in enumerate(extra_symbols, 1)
    ]
    universe = tickers + extras
    selected = select_perp_symbols(universe)

    assert len(selected) == 10
    assert selected[:3] == ("BTC", "ETH", "SOL")
    assert selected[3:] == tuple(extra_symbols[:7])

    candles = {symbol: core_candles["BTC"] for symbol in selected}
    record = build_public_record(
        universe,
        candles,
        request_started_at=started,
        retrieved_at=retrieved,
        request_budget_remaining=2,
    )
    assert record["symbols"] == list(selected)
    assert record["eligible_perp_symbols"] == sorted(["BTC", "ETH", "SOL", *extra_symbols])
    assert record["omitted_perp_symbols"] == extra_symbols[7:]
    assert record["refresh_status"] == "PARTIAL"

    path = tmp_path / "hyperliquid.jsonl"
    append_public_data(path, record)
    assert read_public_data(path) == [record]


def test_perpetual_discovery_rejects_unbounded_universe():
    tickers = [
        Ticker(symbol=f"MARKET{index}", price=1.0)
        for index in range(personal_hyperliquid_public_data.MAX_ELIGIBLE_SYMBOLS + 1)
    ]

    with pytest.raises(HyperliquidPublicDataError, match="bounded"):
        select_perp_symbols(tickers)


def test_record_builder_rejects_naive_times_future_candles_and_contradictions():
    started, retrieved, tickers, candles = _observations()
    with pytest.raises(HyperliquidPublicDataError, match="Timezone-aware"):
        build_public_record(
            tickers,
            candles,
            request_started_at=started.replace(tzinfo=None),
            retrieved_at=retrieved,
            request_budget_remaining=8,
        )

    future = {key: list(rows) for key, rows in candles.items()}
    future["BTC"][0] = {**future["BTC"][0], "time": int((retrieved + timedelta(days=1)).timestamp() * 1000)}
    with pytest.raises(HyperliquidPublicDataError, match="Future"):
        build_public_record(
            tickers,
            future,
            request_started_at=started,
            retrieved_at=retrieved,
            request_budget_remaining=8,
        )

    contradictory = {key: list(rows) for key, rows in candles.items()}
    contradictory["BTC"][0] = {**contradictory["BTC"][0], "low": 101.0}
    with pytest.raises(HyperliquidPublicDataError, match="OHLC"):
        build_public_record(
            tickers,
            contradictory,
            request_started_at=started,
            retrieved_at=retrieved,
            request_budget_remaining=8,
        )


def test_incomplete_provider_results_are_partial_and_never_claim_complete():
    started, retrieved, tickers, candles = _observations()
    incomplete = [ticker for ticker in tickers if ticker.symbol != "SOL"]
    candles["ETH"] = []

    record = build_public_record(
        incomplete,
        candles,
        request_started_at=started,
        retrieved_at=retrieved,
        request_budget_remaining=8,
    )

    assert record["refresh_status"] == "PARTIAL"
    assert set(record["current_marks"]) == {"BTC", "ETH"}
    assert record["daily_bars"]["ETH"] == []
    assert "MISSING_MARK_SOL" in record["provider_errors"]
    assert "DAILY_CANDLES_UNAVAILABLE_ETH" in record["provider_errors"]


def test_fetch_uses_only_three_bounded_daily_requests_and_closes_http_client(
    tmp_path,
    monkeypatch,
):
    gate = _gate(tmp_path / "budget.sqlite3")
    monkeypatch.setattr(hyperliquid_gate_registry, "require_gate", lambda: gate)
    adapter = HyperliquidAdapter()
    _, _, _, candles = _observations()

    async def current_tickers():
        stamp = datetime.now(UTC).isoformat()
        return [
            Ticker(symbol=symbol, price=100.0 + index, timestamp=stamp)
            for index, symbol in enumerate(("BTC", "ETH", "SOL", "DOGE"))
        ]

    adapter.connect_http_only = AsyncMock()
    adapter.get_all_tickers = AsyncMock(side_effect=current_tickers)
    candles["DOGE"] = candles["BTC"]
    adapter.get_candles = AsyncMock(side_effect=lambda symbol, **kwargs: candles[symbol])
    adapter.close = AsyncMock()

    record = asyncio.run(fetch_public_record(adapter, request_budget=gate, pause_seconds=0))

    assert record["refresh_status"] == "COMPLETE"
    adapter.connect_http_only.assert_awaited_once()
    adapter.get_all_tickers.assert_awaited_once()
    assert adapter.get_candles.await_count == 4
    assert record["symbols"] == ["BTC", "ETH", "SOL", "DOGE"]
    assert all(call.kwargs == {"interval": "1d", "lookback": DAILY_CANDLE_LOOKBACK}
               for call in adapter.get_candles.await_args_list)
    adapter.close.assert_awaited_once()
    assert datetime.fromisoformat(record["request_started_at"]) <= datetime.fromisoformat(
        record["retrieved_at"]
    )


def test_fetch_rejects_a_budget_other_than_the_installed_shared_gate(tmp_path, monkeypatch):
    installed = _gate(tmp_path / "installed.sqlite3")
    wrong = _gate(tmp_path / "other.sqlite3")
    monkeypatch.setattr(hyperliquid_gate_registry, "require_gate", lambda: installed)
    adapter = HyperliquidAdapter()
    adapter.connect_http_only = AsyncMock()

    with pytest.raises(HyperliquidPublicDataError, match="does not match"):
        asyncio.run(fetch_public_record(adapter, request_budget=wrong, pause_seconds=0))

    adapter.connect_http_only.assert_not_awaited()


def test_public_data_journal_restart_integrity_and_api_are_read_only(tmp_path):
    data_path = tmp_path / "hyperliquid.jsonl"
    record = _record()
    append_public_data(data_path, record)

    assert read_public_data(data_path) == [record]
    assert public_data_read_model(data_path)["latest"] == record
    assert public_data_read_model(data_path)["freshness"]["status"] == "RECENT_LOCAL_RETRIEVAL"
    with TestClient(create_app(
        tmp_path / "paper.jsonl",
        tmp_path / "yahoo.jsonl",
        data_path,
    )) as client:
        response = client.get("/api/market-data/hyperliquid")
        assert response.status_code == 200
        assert response.json()["latest"] == record
        assert response.json()["freshness"]["provider_timestamp_available"] is False
        assert response.json()["provider_errors"] == []
        assert response.json()["paper_entry_authorized"] is False
        assert client.post("/api/market-data/hyperliquid").status_code == 405
        assert client.get("/api/paper/status").json()["genuine_forward_paper"] is False

    data_path.write_bytes(data_path.read_bytes().replace(b"100.0", b"200.0", 1))
    with pytest.raises(HyperliquidPublicDataError, match="Unreadable"):
        read_public_data(data_path)


def test_hyperliquid_journal_rejects_replay_and_refresh_cooldown(tmp_path):
    data_path = tmp_path / "hyperliquid.jsonl"
    record = _record()
    append_public_data(data_path, record)
    with pytest.raises(HyperliquidPublicDataError, match="Duplicate"):
        append_public_data(data_path, record)

    now = datetime.fromisoformat(record["retrieved_at"])
    with pytest.raises(HyperliquidPublicDataError, match="cooldown"):
        require_manual_refresh_spacing(data_path, now=now + timedelta(seconds=10))
    with pytest.raises(HyperliquidPublicDataError, match="clock"):
        require_manual_refresh_spacing(data_path, now=now - timedelta(seconds=1))
    require_manual_refresh_spacing(data_path, now=now + timedelta(seconds=31))


def test_read_model_does_not_label_old_snapshot_as_recent(tmp_path):
    data_path = tmp_path / "hyperliquid.jsonl"
    old_record = _record(datetime.now(UTC) - timedelta(minutes=5))
    append_public_data(data_path, old_record)

    freshness = public_data_read_model(data_path)["freshness"]

    assert freshness["status"] == "STALE_LOCAL_RETRIEVAL"
    assert freshness["basis"] == "LOCAL_RETRIEVAL_TIME_ONLY"
    assert freshness["provider_timestamp_available"] is False


def test_manual_cli_requires_confirmation_and_budget_init_makes_no_request(tmp_path, capsys):
    path = tmp_path / "budget.sqlite3"
    with pytest.raises(SystemExit):
        main([
            "--initialize-hyperliquid-public-data-budget",
            "--hyperliquid-budget-path",
            str(path),
        ])

    main([
        "--initialize-hyperliquid-public-data-budget",
        "--confirm-read-only-public-data",
        "--hyperliquid-budget-path",
        str(path),
    ])
    result = json.loads(capsys.readouterr().out)
    assert result["maximum_requests"] == 12
    assert result["network_requests_made"] == 0
    assert path.is_file()
