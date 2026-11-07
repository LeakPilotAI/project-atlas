"""Run a bounded multi-tick incremental V3 PAPER demo in disposable custody."""
from __future__ import annotations

import argparse
import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path


def run_incremental_demo(*, scenario="take_profit"):
    from app.investment.quality_dips_paper import initialize_paper_account
    from app.services.disposable_v3_incremental import (
        execute_incremental_test_v3_tick, inspect_incremental_test_v3_recovery)

    scenarios = {
        "take_profit": [(101, 101.1), (79.9, 80), (80.9, 81), (84, 84.1)],
        "stop_loss": [(101, 101.1), (79.9, 80), (75, 75.1), (74, 74.1)],
        "gap_down": [(101, 101.1), (79.9, 80), (60, 60.1), (59, 59.1)],
        "no_entry": [(111, 111.1), (110, 110.1), (109, 109.1), (108, 108.1)],
    }
    if scenario not in scenarios:
        raise ValueError("INCREMENTAL_V3_DEMO_SCENARIO_UNKNOWN")
    start = datetime(2026, 11, 7, tzinfo=UTC)
    research = {"symbol": "MSFT", "source_verified": True,
                "timestamp": start.isoformat(),
                "normalization_value": {"conservative": 95, "base": 100, "optimistic": 105},
                "quality_score": 80, "fundamentals_score": 80,
                "valuation_score": 70, "drawdown_percentile": 80,
                "evidence_quality": "HIGH", "thesis": "INTACT", "value_trap": False}
    observation = {"observation_id": "incremental-synthetic-demo",
                   "symbol": "MSFT", "evidence_class": "TEST_DATA"}
    with tempfile.TemporaryDirectory(prefix="atlas-incremental-v3-test-") as directory:
        path = Path(directory) / "paper.jsonl"
        initialize_paper_account(account_id="demo", opening_cash=1000,
                                 fee_bps_per_side=2, max_open_positions=1,
                                 data_provenance="TEST_DATA", path=path)
        actions = []
        for index, (bid, ask) in enumerate(scenarios[scenario]):
            now = start + timedelta(seconds=index)
            quote = {"symbol": "MSFT", "state": "FRESH", "bid": bid,
                     "ask": ask, "bid_lots": 5, "ask_lots": 5,
                     "timestamp": now.isoformat(),
                     "timestamp_basis": "PROVIDER_EVENT_TIMESTAMP"}
            tick = execute_incremental_test_v3_tick(
                path=path, account_id="demo", observation=observation,
                research=research, quote=quote, now=now)
            actions.append(tick["action"])
        report = inspect_incremental_test_v3_recovery(path=path, account_id="demo")
        if report["recovery_status"] != "CLEAN" or not report["cash_reconciled"]:
            raise ValueError("INCREMENTAL_V3_DEMO_RECOVERY_NOT_CLEAN")
        return {"schema": "ATLAS_INCREMENTAL_V3_DEMO_V1",
                "scenario": scenario, "actions": actions,
                "completed_ticks": report["completed_ticks"],
                "open_positions": report["open_positions"],
                "net_realized_pnl": report["net_realized_pnl"],
                "cash_reconciled": report["cash_reconciled"],
                "recovery_status": report["recovery_status"],
                "data_source": "SYNTHETIC", "evidence_class": "TEST_DATA",
                "provider_authenticated": False,
                "research_provenance_attested": False,
                "forward_trading_authorized": False,
                "live_order_authorized": False}


def main():
    parser = argparse.ArgumentParser(description="Disposable incremental V3 PAPER simulation")
    parser.add_argument("--scenario", choices=("take_profit", "stop_loss", "gap_down", "no_entry"),
                        default="take_profit")
    args = parser.parse_args()
    print(json.dumps(run_incremental_demo(scenario=args.scenario), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
