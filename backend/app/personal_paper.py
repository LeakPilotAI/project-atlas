"""Standalone loopback-only Quality Dips PAPER application for TEST DATA."""

from __future__ import annotations

import argparse
import json
import os
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.investment.quality_dips_paper import (
    accounting_snapshot,
    close_lot,
    initialize_test_account,
    open_lot,
    portfolio_snapshot,
    read_events,
    record_decision,
)
from app.investment.quality_dips_paper_exit_policy import evaluate_exit
from app.investment.quality_dips_v3 import build_v3_entry_plan

ACCOUNT_ID = "atlas-personal-qd-test-data-v1"
OPENING_CASH = 1000.0
ENTRY_NOTIONAL = 100.0
FEE_BPS_PER_SIDE = 2.0
TEST_FIXTURE_ID = "qd-v3-offline-test-fixture-v1"
TIMEZONE = ZoneInfo("America/New_York")
DEFAULT_JOURNAL = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "personal_paper_test"
    / "quality_dips_paper.jsonl"
)


def _now() -> datetime:
    return datetime.now(UTC)


def _report_date(value: str | None) -> date:
    if value is None:
        return _now().astimezone(TIMEZONE).date()
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise ValueError("date must use YYYY-MM-DD")
    return parsed


def _equity_drawdown(events: list[dict[str, Any]]) -> dict[str, float]:
    cash = 0.0
    positions: dict[str, dict[str, float]] = {}
    peak = 0.0
    max_drawdown = 0.0
    max_drawdown_pct = 0.0

    for row in events:
        event = row.get("event")
        if event == "account_opened":
            cash = float(row["opening_cash"])
        elif event == "open_lot":
            notional = float(row["paper_notional_dollars"])
            entry_fee = float(row.get("entry_fee") or 0)
            cash -= notional + entry_fee
            positions[row["lot_id"]] = {
                "quantity": float(row["quantity_shares"]),
                "price": float(row["fill_price"]),
                "fee_bps": float(row.get("fee_bps_per_side") or 0),
            }
        elif event == "mark_lot" and row.get("lot_id") in positions:
            positions[row["lot_id"]]["price"] = float(row["market_price"])
        elif event == "close_lot":
            position = positions.pop(row["lot_id"], None)
            if position is not None:
                cash += (
                    float(row["quantity_shares"]) * float(row["exit_price"])
                    - float(row.get("exit_fee") or 0)
                )
        else:
            continue

        equity = cash + sum(
            position["quantity"] * position["price"]
            * (1 - position["fee_bps"] / 10000)
            for position in positions.values()
        )
        peak = max(peak, equity)
        drawdown = max(0.0, peak - equity)
        max_drawdown = max(max_drawdown, drawdown)
        if peak > 0:
            max_drawdown_pct = max(max_drawdown_pct, drawdown / peak * 100)

    return {
        "max_drawdown": round(max_drawdown, 8),
        "max_drawdown_pct": round(max_drawdown_pct, 8),
    }


def build_daily_report(
    events: list[dict[str, Any]],
    report_day: date,
) -> dict[str, Any]:
    account = accounting_snapshot(events, account_id=ACCOUNT_ID)
    if account is None:
        return {
            "schema": "ATLAS_PERSONAL_PAPER_DAILY_REPORT_V1",
            "status": "UNAVAILABLE",
            "date": report_day.isoformat(),
            "data_provenance": "TEST_DATA",
            "reason": "TEST_DATA_ACCOUNT_NOT_INITIALIZED",
            "startup_authorized": False,
        }

    day_key = report_day.isoformat()

    def in_day(row: dict[str, Any], field: str) -> bool:
        value = row.get(field)
        if not isinstance(value, str):
            return False
        try:
            timestamp = datetime.fromisoformat(value)
        except ValueError:
            return False
        if timestamp.tzinfo is None:
            return False
        return timestamp.astimezone(TIMEZONE).date().isoformat() == day_key

    opens = [
        row for row in events
        if row.get("event") == "open_lot"
        and row.get("account_id") == ACCOUNT_ID
        and in_day(row, "timestamp")
    ]
    closes = [
        row for row in events
        if row.get("event") == "close_lot"
        and row.get("account_id") == ACCOUNT_ID
        and in_day(row, "timestamp")
    ]
    wins = sum(float(row.get("net_realized_pnl") or 0) > 0 for row in closes)
    losses = sum(float(row.get("net_realized_pnl") or 0) < 0 for row in closes)
    gross = sum(float(row.get("realized_pnl") or 0) for row in closes)
    net = sum(float(row.get("net_realized_pnl") or 0) for row in closes)
    daily_fees = sum(float(row.get("entry_fee") or 0) for row in opens) + sum(
        float(row.get("exit_fee") or 0) for row in closes
    )
    portfolio = portfolio_snapshot(events)
    return {
        "schema": "ATLAS_PERSONAL_PAPER_DAILY_REPORT_V1",
        "status": "COMPLETE",
        "date": day_key,
        "strategy": "QUALITY_DIPS_V3",
        "data_provenance": "TEST_DATA",
        "source_fixture": TEST_FIXTURE_ID,
        "source_revision": len(events),
        "currency": "SIMULATED_USD",
        "closed_trades": len(closes),
        "opened_trades": len(opens),
        "wins": wins,
        "losses": losses,
        "win_rate_pct": round(wins / len(closes) * 100, 4) if closes else None,
        "gross_realized_pnl": round(gross, 8),
        "fees_and_costs": round(daily_fees, 8),
        "net_realized_pnl": round(net, 8),
        "cash_reconciled": account["cash_reconciled"],
        "current_available_cash": account["available_cash"],
        "current_open_positions": account["open_positions"],
        "max_drawdown_since_inception": _equity_drawdown(events),
        "portfolio_summary": portfolio["summary"],
        "generated_at": _now().isoformat(),
        "startup_authorized": False,
        "production_authorized": False,
        "genuine_forward_paper": False,
        "operational_acceptance": False,
    }


def run_test_data_session(path: Path = DEFAULT_JOURNAL) -> dict[str, Any]:
    """Run the existing V3 decision and PAPER lot lifecycle on fixed TEST DATA."""
    path = Path(path)
    initialize_test_account(
        account_id=ACCOUNT_ID,
        opening_cash=OPENING_CASH,
        fee_bps_per_side=FEE_BPS_PER_SIDE,
        max_open_positions=1,
        path=path,
    )
    plan = build_v3_entry_plan(
        symbol="MSFT",
        current_price=84.0,
        normalization={"conservative": 100.0, "base": 100.0, "optimistic": 100.0},
        quality_score=90,
        fundamentals_score=85,
        valuation_score=80,
        drawdown_percentile=80,
        evidence_quality="HIGH",
        thesis_intact=True,
        value_trap=False,
    )
    reached = [
        row["level"]
        for row in plan["entry_ladder"]["levels"]
        if row["reached"] is True
    ]
    if plan["patient_state"] not in {"ACCUMULATION", "DEEP_VALUE", "GENERATIONAL"} or "L1" not in reached:
        raise RuntimeError("fixed TEST_DATA no longer produces the expected V3 PAPER entry")
    observation = {
        "observation_id": f"{TEST_FIXTURE_ID}:entry",
        "symbol": "MSFT",
        "price": 84.0,
        "source_timestamp": "2026-01-02T15:00:00+00:00",
        "classification": plan["patient_state"],
        "strategy_version": "QUALITY_DIPS_V3",
        "policy_version": "quality-dips-v3-mos-15-20-25-30-v1",
        "evidence_class": "TEST_DATA",
        "prediction": plan,
        "fixture_id": TEST_FIXTURE_ID,
    }
    record_decision(
        observation,
        decision="PAPER_OPEN_L1",
        reason="Existing V3 entry policy applied to fixed offline TEST_DATA",
        account_id=ACCOUNT_ID,
        path=path,
    )
    lot = open_lot(
        observation,
        level="L1",
        paper_notional_dollars=ENTRY_NOTIONAL,
        account_id=ACCOUNT_ID,
        fee_bps_per_side=FEE_BPS_PER_SIDE,
        path=path,
    )
    exit_observation = {
        "classification": "THESIS_BROKEN",
        "evidence_class": "TEST_DATA",
        "fixture_id": TEST_FIXTURE_ID,
        "prediction": {"patient_state": "THESIS_BROKEN", "blockers": []},
    }
    exit_decision = evaluate_exit(exit_observation)
    if not exit_decision["terminal"]:
        raise RuntimeError("existing Quality Dips exit policy refused fixed TEST_DATA exit")
    closed = close_lot(
        lot["lot_id"],
        exit_price=86.0,
        reason=exit_decision["terminal_reason"],
        closed_at=_now().isoformat(),
        path=path,
    )
    events = read_events(path)
    snapshot = portfolio_snapshot(events)
    closed_at = datetime.fromisoformat(closed["timestamp"])
    report = build_daily_report(events, closed_at.astimezone(TIMEZONE).date())
    return {
        "schema": "ATLAS_PERSONAL_PAPER_TEST_DATA_RESULT_V1",
        "data_provenance": "TEST_DATA",
        "fixture_id": TEST_FIXTURE_ID,
        "strategy_decision": plan,
        "entry": lot,
        "exit": closed,
        "portfolio": snapshot,
        "daily_report": report,
        "live_order_adapter_connected": False,
        "external_connections_used": False,
        "genesis_accessed": False,
    }


def create_app(journal_path: Path = DEFAULT_JOURNAL) -> FastAPI:
    path = Path(journal_path)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        events = read_events(path)
        portfolio_snapshot(events)
        yield
        events = read_events(path)
        portfolio_snapshot(events)

    app = FastAPI(
        title="Atlas Personal Quality Dips PAPER — TEST DATA",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        return _DASHBOARD_HTML

    @app.get("/api/paper/status")
    def status() -> dict[str, Any]:
        events = read_events(path)
        return {
            "schema": "ATLAS_PERSONAL_PAPER_LOCAL_STATUS_V1",
            "runtime": "STANDALONE_LOOPBACK_QUALITY_DIPS_PAPER",
            "data_provenance": "TEST_DATA",
            "last_record_at": events[-1].get("timestamp") if events else None,
            "record_count": len(events),
            "broker_order_created": False,
            "live_order_adapter_connected": False,
            "provider_connections_used": False,
            "external_connections_used": False,
            "genesis_accessed": False,
            "genuine_forward_paper": False,
            "operational_acceptance": False,
            "startup_authorized": False,
            "production_authorized": False,
        }

    @app.get("/api/paper/portfolio")
    def portfolio() -> dict[str, Any]:
        return portfolio_snapshot(read_events(path))

    @app.get("/api/paper/trades")
    def trades() -> dict[str, Any]:
        events = read_events(path)
        return {
            "schema": "ATLAS_PERSONAL_PAPER_TRADES_V1",
            "data_provenance": "TEST_DATA",
            "source_revision": len(events),
            "transactions": [
                row for row in events
                if row.get("event") in {"open_lot", "mark_lot", "close_lot"}
            ],
            "decisions": [row for row in events if row.get("event") == "decision"],
        }

    @app.get("/api/paper/report")
    def report(day: str | None = Query(default=None, alias="date")) -> dict[str, Any]:
        try:
            parsed_day = _report_date(day)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return build_daily_report(read_events(path), parsed_day)

    return app


_DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Atlas Personal PAPER — TEST DATA</title>
  <style>
    body{font:16px system-ui,sans-serif;max-width:980px;margin:2rem auto;padding:0 1rem;color:#17212b}
    .banner{padding:1rem;background:#fff2cc;border:1px solid #d6aa35;font-weight:700}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem}
    section{border:1px solid #ccd3da;border-radius:8px;padding:1rem;margin:1rem 0}
    pre{white-space:pre-wrap;overflow-wrap:anywhere}
    #error{color:#a00}.muted{color:#52606d}
  </style>
</head>
<body>
  <h1>Atlas Personal Quality Dips PAPER</h1>
  <p class="banner">TEST DATA ONLY — offline deterministic demonstration, not genuine forward PAPER or market activity.</p>
  <p id="freshness" class="muted">Loading local journal…</p>
  <p id="error" role="alert"></p>
  <div class="grid">
    <section><h2>Portfolio</h2><pre id="portfolio">Loading…</pre></section>
    <section><h2>Daily report</h2><pre id="report">Loading…</pre></section>
  </div>
  <section><h2>Durable simulated transactions</h2><pre id="trades">Loading…</pre></section>
  <script>
    async function readLocal(path) {
      const response = await fetch(path, {cache: "no-store"});
      if (!response.ok) throw new Error(path + " returned HTTP " + response.status);
      return response.json();
    }
    async function refresh() {
      try {
        const [status, portfolio, report, trades] = await Promise.all([
          readLocal("/api/paper/status"), readLocal("/api/paper/portfolio"),
          readLocal("/api/paper/report"), readLocal("/api/paper/trades")
        ]);
        document.querySelector("#freshness").textContent =
          "TEST DATA · journal records: " + status.record_count +
          " · last local transaction: " + (status.last_record_at || "none");
        document.querySelector("#portfolio").textContent = JSON.stringify(portfolio, null, 2);
        document.querySelector("#report").textContent = JSON.stringify(report, null, 2);
        document.querySelector("#trades").textContent = JSON.stringify(trades, null, 2);
        document.querySelector("#error").textContent = "";
      } catch (error) {
        document.querySelector("#freshness").textContent = "Local PAPER data unavailable.";
        document.querySelector("#error").textContent = String(error);
      }
    }
    refresh();
  </script>
</body>
</html>"""


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Standalone loopback Quality Dips PAPER app using TEST DATA only."
    )
    parser.add_argument("--data-path", type=Path, default=DEFAULT_JOURNAL)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--run-test-data",
        action="store_true",
        help="execute the fixed offline V3 entry/exit lifecycle and print its records",
    )
    args = parser.parse_args(argv)
    if args.run_test_data:
        print(json.dumps(run_test_data_session(args.data_path), indent=2, sort_keys=True))
        return
    if not 1024 <= args.port <= 65535:
        parser.error("--port must be between 1024 and 65535")
    import signal

    import uvicorn

    class LocalPaperServer(uvicorn.Server):
        def handle_exit(self, sig, frame):
            if sig == getattr(signal, "SIGBREAK", None):
                sig = signal.SIGINT
            super().handle_exit(sig, frame)

    server = LocalPaperServer(
        uvicorn.Config(
            create_app(args.data_path),
            host="127.0.0.1",
            port=args.port,
            log_level="info",
            access_log=False,
        )
    )
    try:
        server.run()
    except KeyboardInterrupt:
        pass
    if not server.started:
        raise SystemExit(3)


app = create_app(Path(os.environ.get("ATLAS_PERSONAL_PAPER_DATA_PATH", DEFAULT_JOURNAL)))

if __name__ == "__main__":
    main()
