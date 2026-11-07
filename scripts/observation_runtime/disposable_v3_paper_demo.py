"""One-shot synthetic Quality Dips V3 PAPER demo, never a forward runner.

No credentials, network, custody, external path, startup, or broker access.
The entire TEST_DATA journal is created inside an automatically removed temp dir.
"""
from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path


def run_demo() -> dict:
    from app.investment.quality_dips_paper import initialize_paper_account
    from app.services.personal_paper_fixture_executor import rehearse_disposable_v3_strategy_session

    start = datetime(2026, 11, 7, tzinfo=UTC)
    times = [start + timedelta(seconds=i) for i in range(4)]
    prices = [(101, 101.1), (79.9, 80), (80.9, 81), (84, 84.1)]
    quotes = [{"symbol": "MSFT", "state": "FRESH", "bid": bid, "ask": ask,
               "bid_lots": 5, "ask_lots": 5, "timestamp": stamp.isoformat(),
               "timestamp_basis": "PROVIDER_EVENT_TIMESTAMP"}
              for stamp, (bid, ask) in zip(times, prices, strict=True)]
    research = {"symbol": "MSFT", "source_verified": True,
                "timestamp": start.isoformat(),
                "normalization_value": {"conservative": 95, "base": 100, "optimistic": 105},
                "quality_score": 80, "fundamentals_score": 80,
                "valuation_score": 70, "drawdown_percentile": 80,
                "evidence_quality": "HIGH", "thesis": "INTACT", "value_trap": False}
    observation = {"observation_id": "synthetic-v3-demo", "symbol": "MSFT",
                   "evidence_class": "TEST_DATA"}
    with tempfile.TemporaryDirectory(prefix="atlas-v3-test-only-") as temp:
        path = Path(temp) / "paper.jsonl"
        initialize_paper_account(account_id="demo", opening_cash=1000,
                                 fee_bps_per_side=2, max_open_positions=1,
                                 data_provenance="TEST_DATA", path=path)
        result = rehearse_disposable_v3_strategy_session(
            path=path, account_id="demo", observation=observation,
            research=research, quotes=quotes, times=times)
        if result["open_positions"] != 0 or result["cash_reconciled"] is not True:
            raise ValueError("DISPOSABLE_V3_DEMO_NOT_RECONCILED")
        return {"schema": "ATLAS_DISPOSABLE_V3_DEMO_V1",
                "evidence_class": "TEST_DATA", "data_source": "SYNTHETIC",
                "strategy": result["strategy"],
                "actions": [row["action"] for row in result["actions"]],
                "net_realized_pnl": result["net_realized_pnl"],
                "cash_reconciled": result["cash_reconciled"],
                "provider_authenticated": False,
                "research_provenance_attested": False,
                "forward_trading_authorized": False,
                "live_order_authorized": False}


def main() -> int:
    print(json.dumps(run_demo(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
