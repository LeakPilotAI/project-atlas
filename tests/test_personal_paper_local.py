"""Local Quality Dips PAPER application tests using offline TEST DATA only."""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest
from app.investment.quality_dips_paper import (
    accounting_snapshot,
    initialize_test_account,
    open_lot,
    read_events,
)
from app.personal_paper import (
    ACCOUNT_ID,
    DEFAULT_FORWARD_JOURNAL,
    DEFAULT_HYPERLIQUID_MARKET_DATA,
    DEFAULT_JOURNAL,
    DEFAULT_MARKET_DATA,
    DEFAULT_STRATEGY_OBSERVATIONS,
    FEE_BPS_PER_SIDE,
    OPENING_CASH,
    build_daily_report,
    create_app,
    run_test_data_session,
)
from app.services.personal_paper_observations import process_public_observations
from fastapi.testclient import TestClient
from test_personal_paper_observations import _research, _write_observations


def _observation(observation_id: str = "offline-test-observation") -> dict:
    return {
        "observation_id": observation_id,
        "symbol": "MSFT",
        "price": 84.0,
        "classification": "ACCUMULATION",
        "evidence_class": "TEST_DATA",
    }


def test_offline_v3_entry_and_terminal_exit_reconcile_cash_and_costs(tmp_path: Path):
    journal = tmp_path / "quality-dips.jsonl"

    result = run_test_data_session(journal)
    rows = read_events(journal)
    portfolio = result["portfolio"]
    account = portfolio["accounting"]

    assert [row["event"] for row in rows] == [
        "account_opened",
        "decision",
        "open_lot",
        "close_lot",
    ]
    assert result["data_provenance"] == "TEST_DATA"
    assert result["strategy_decision"]["patient_state"] == "ACCUMULATION"
    assert result["entry"]["evidence_class"] == "TEST_DATA"
    assert result["entry"]["broker_order_created"] is False
    assert result["entry"]["entry_fee"] == pytest.approx(0.02)
    assert result["exit"]["reason"] == "THESIS_BROKEN"
    assert result["exit"]["exit_fee"] > 0
    assert result["exit"]["net_realized_pnl"] == pytest.approx(
        result["exit"]["realized_pnl"]
        - result["exit"]["entry_fee"]
        - result["exit"]["exit_fee"]
    )
    assert portfolio["summary"]["closed_lots"] == 1
    assert portfolio["summary"]["open_lots"] == 0
    assert account["cash_reconciled"] is True
    assert account["cash_difference"] == 0
    assert account["fees_paid"] == pytest.approx(
        result["entry"]["entry_fee"] + result["exit"]["exit_fee"]
    )
    assert account["available_cash"] == pytest.approx(
        OPENING_CASH + result["exit"]["net_realized_pnl"]
    )
    assert result["daily_report"]["data_provenance"] == "TEST_DATA"
    assert result["daily_report"]["closed_trades"] == 1
    assert result["daily_report"]["fees_and_costs"] == pytest.approx(account["fees_paid"])
    assert result["daily_report"]["cash_reconciled"] is True
    assert result["live_order_adapter_connected"] is False
    assert result["external_connections_used"] is False


def test_test_data_run_is_restart_safe_and_idempotent(tmp_path: Path):
    journal = tmp_path / "quality-dips.jsonl"
    first = run_test_data_session(journal)
    original = journal.read_bytes()

    reloaded_events = read_events(journal)
    second_account = accounting_snapshot(reloaded_events, account_id=ACCOUNT_ID)
    retry = run_test_data_session(journal)

    assert second_account == first["portfolio"]["accounting"]
    assert journal.read_bytes() == original
    assert retry["entry"]["lot_id"] == first["entry"]["lot_id"]
    assert retry["exit"]["event_id"] == first["exit"]["event_id"]
    assert retry["portfolio"]["accounting"]["available_cash"] == pytest.approx(
        first["portfolio"]["accounting"]["available_cash"]
    )


def test_account_enforces_test_data_provenance_cash_and_position_limit(tmp_path: Path):
    journal = tmp_path / "quality-dips.jsonl"
    initialize_test_account(
        account_id=ACCOUNT_ID,
        opening_cash=OPENING_CASH,
        fee_bps_per_side=FEE_BPS_PER_SIDE,
        path=journal,
    )
    with pytest.raises(ValueError, match="TEST_DATA"):
        open_lot(
            {**_observation(), "evidence_class": "FORWARD_COLLECTION"},
            level="L1",
            paper_notional_dollars=100,
            account_id=ACCOUNT_ID,
            fee_bps_per_side=FEE_BPS_PER_SIDE,
            path=journal,
        )
    first = open_lot(
        _observation(),
        level="L1",
        paper_notional_dollars=100,
        account_id=ACCOUNT_ID,
        fee_bps_per_side=FEE_BPS_PER_SIDE,
        path=journal,
    )
    with pytest.raises(ValueError, match="position limit"):
        open_lot(
            _observation("second-observation"),
            level="L1",
            paper_notional_dollars=100,
            account_id=ACCOUNT_ID,
            fee_bps_per_side=FEE_BPS_PER_SIDE,
            path=journal,
        )
    assert first["account_id"] == ACCOUNT_ID
    assert accounting_snapshot(read_events(journal))["available_cash"] < OPENING_CASH


def test_daily_report_is_derived_from_the_test_journal(tmp_path: Path):
    result = run_test_data_session(tmp_path / "quality-dips.jsonl")
    report_day = date.fromisoformat(result["daily_report"]["date"])
    repeated = build_daily_report(read_events(tmp_path / "quality-dips.jsonl"), report_day)

    assert repeated["source_revision"] == result["daily_report"]["source_revision"]
    assert repeated["net_realized_pnl"] == result["daily_report"]["net_realized_pnl"]
    assert repeated["fees_and_costs"] == result["daily_report"]["fees_and_costs"]
    assert repeated["wins"] == 1
    assert repeated["losses"] == 0
    assert repeated["max_drawdown_since_inception"]["max_drawdown"] >= 0


def test_read_only_dashboard_api_uses_the_durable_journal(tmp_path: Path):
    journal = tmp_path / "quality-dips.jsonl"
    with TestClient(
        create_app(
            journal,
            forward_journal_path=tmp_path / "forward.jsonl",
            strategy_observations_path=tmp_path / "strategy.jsonl",
        )
    ) as client:
        before = client.get("/api/paper/portfolio").json()
        assert before["accounting"] is None
        assert "TEST DATA ONLY" in client.get("/").text

        result = run_test_data_session(journal)
        portfolio = client.get("/api/paper/portfolio").json()
        trades = client.get("/api/paper/trades").json()
        report = client.get(
            "/api/paper/report",
            params={"date": result["daily_report"]["date"]},
        ).json()
        status = client.get("/api/paper/status").json()

        assert portfolio["lots"][0]["entry"] == result["entry"]
        assert portfolio["lots"][0]["terminal"] == result["exit"]
        assert [row["event"] for row in trades["transactions"]] == ["open_lot", "close_lot"]
        assert trades["transactions"][0] == result["entry"]
        assert trades["transactions"][1] == result["exit"]
        assert report["net_realized_pnl"] == result["daily_report"]["net_realized_pnl"]
        assert status["data_provenance"] == "TEST_DATA"
        assert status["live_order_adapter_connected"] is False
        assert status["genuine_forward_paper"] is False
        assert status["operational_acceptance"] is False
        assert client.post("/api/paper/trades").status_code == 405
        assert client.get("/api/paper/report", params={"date": "tomorrow"}).status_code == 422


def _free_loopback_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_server(
    backend: Path,
    journal: Path,
    port: int,
    *,
    market_data: Path = DEFAULT_MARKET_DATA,
    hyperliquid_data: Path = DEFAULT_HYPERLIQUID_MARKET_DATA,
    forward_journal: Path = DEFAULT_FORWARD_JOURNAL,
    strategy_observations: Path = DEFAULT_STRATEGY_OBSERVATIONS,
) -> subprocess.Popen:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(backend) + os.pathsep + env.get("PYTHONPATH", "")
    env["ATLAS_PERSONAL_PAPER_DATA_PATH"] = str(journal)
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "app.personal_paper",
            "--data-path",
            str(journal),
            "--market-data-path",
            str(market_data),
            "--hyperliquid-data-path",
            str(hyperliquid_data),
            "--forward-data-path",
            str(forward_journal),
            "--strategy-observations-path",
            str(strategy_observations),
            "--port",
            str(port),
        ],
        cwd=backend,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=flags,
    )


def _get_json(url: str) -> dict:
    with urlopen(url, timeout=1) as response:
        return json.loads(response.read().decode("utf-8"))


def _wait_for_server(process: subprocess.Popen, url: str) -> None:
    deadline = time.monotonic() + 15
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = process.communicate(timeout=1)[0]
            raise AssertionError(f"standalone server exited early:\n{output}")
        try:
            _get_json(url)
            return
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(0.1)
    raise AssertionError(f"standalone server did not become ready: {last_error}")


def _stop_server_cleanly(process: subprocess.Popen) -> str:
    if process.poll() is None:
        if os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            process.send_signal(signal.SIGINT)
    try:
        output = process.communicate(timeout=15)[0]
    except subprocess.TimeoutExpired as exc:
        pytest.fail(f"standalone server did not stop cleanly: {exc}")
    assert process.returncode == 0, output
    assert "Application shutdown complete" in output
    return output


def test_real_loopback_start_transaction_dashboard_restart_and_clean_stop(tmp_path: Path):
    backend = Path(__file__).resolve().parents[1] / "backend"
    journal = tmp_path / "acceptance" / "quality-dips.jsonl"
    forward_journal = tmp_path / "acceptance" / "forward.jsonl"
    strategy_observations = tmp_path / "acceptance" / "strategy.jsonl"
    market_data, hyperliquid_data = _write_observations(
        tmp_path,
        datetime.now(UTC),
    )
    process_public_observations(
        market_data_path=market_data,
        hyperliquid_data_path=hyperliquid_data,
        forward_journal_path=forward_journal,
        strategy_observation_path=strategy_observations,
        research_rows=_research(datetime.now(UTC)),
    )
    port = _free_loopback_port()
    base_url = f"http://127.0.0.1:{port}"
    server = _start_server(
        backend,
        journal,
        port,
        market_data=market_data,
        hyperliquid_data=hyperliquid_data,
        forward_journal=forward_journal,
        strategy_observations=strategy_observations,
    )
    try:
        _wait_for_server(server, base_url + "/api/paper/status")
        page = urlopen(base_url + "/", timeout=2).read().decode("utf-8")
        assert "TEST DATA ONLY" in page
        first_status = _get_json(base_url + "/api/paper/status")
        assert first_status["record_count"] == 0
        assert first_status["forward_paper"]["paper_positions"] == 0
        assert _get_json(base_url + "/api/strategy/observations")["record_count"] == 4
        forward_report = _get_json(base_url + "/api/paper/forward/report")
        assert forward_report["genuine_forward_paper"] is False
        assert forward_report["current_available_cash"] == 1000.0
        assert forward_report["closed_trades"] == 0

        env = os.environ.copy()
        env["PYTHONPATH"] = str(backend) + os.pathsep + env.get("PYTHONPATH", "")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "app.personal_paper",
                "--data-path",
                str(journal),
                "--run-test-data",
            ],
            cwd=backend,
            env=env,
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        execution = json.loads(result.stdout)
        portfolio = _get_json(base_url + "/api/paper/portfolio")
        trades = _get_json(base_url + "/api/paper/trades")
        report = _get_json(
            base_url + "/api/paper/report?date=" + execution["daily_report"]["date"]
        )

        assert portfolio["lots"][0]["entry"] == execution["entry"]
        assert portfolio["lots"][0]["terminal"] == execution["exit"]
        assert [row["event"] for row in trades["transactions"]] == ["open_lot", "close_lot"]
        assert trades["transactions"][0] == execution["entry"]
        assert trades["transactions"][1] == execution["exit"]
        assert report["net_realized_pnl"] == execution["daily_report"]["net_realized_pnl"]
        _stop_server_cleanly(server)
        server = None

        server = _start_server(
            backend,
            journal,
            port,
            market_data=market_data,
            hyperliquid_data=hyperliquid_data,
            forward_journal=forward_journal,
            strategy_observations=strategy_observations,
        )
        _wait_for_server(server, base_url + "/api/paper/status")
        recovered = _get_json(base_url + "/api/paper/portfolio")
        recovered_trades = _get_json(base_url + "/api/paper/trades")
        recovered_status = _get_json(base_url + "/api/paper/status")
        recovered_forward = _get_json(base_url + "/api/paper/forward/portfolio")
        recovered_observations = _get_json(base_url + "/api/strategy/observations")
        assert recovered["accounting"]["cash_reconciled"] is True
        assert recovered["accounting"]["available_cash"] == pytest.approx(
            execution["portfolio"]["accounting"]["available_cash"]
        )
        assert recovered_trades["transactions"] == trades["transactions"]
        assert recovered_status["record_count"] == first_status["record_count"] + 4
        assert recovered_status["live_order_adapter_connected"] is False
        assert recovered_status["external_connections_used"] is False
        assert recovered_forward["accounting"]["cash_reconciled"] is True
        assert recovered_forward["accounting"]["available_cash"] == 1000.0
        assert recovered_observations["record_count"] == 4
    finally:
        if server is not None and server.poll() is None:
            _stop_server_cleanly(server)


def test_default_data_journal_is_outside_the_main_paper_ledger():
    assert DEFAULT_JOURNAL.name == "quality_dips_paper.jsonl"
    assert "personal_paper_test" in str(DEFAULT_JOURNAL)
    assert "paper_journal.jsonl" not in str(DEFAULT_JOURNAL)


def test_standalone_import_does_not_load_main_app_workers():
    backend = Path(__file__).resolve().parents[1] / "backend"
    code = (
        "import sys; import app.personal_paper; "
        "assert 'app.main' not in sys.modules; "
        "assert 'app.services.daily_paper_recap' not in sys.modules; "
        "assert 'app.services.quality_dip_scanner' not in sys.modules"
    )
    subprocess.run([sys.executable, "-c", code], cwd=backend, check=True, timeout=15)
