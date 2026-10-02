from __future__ import annotations

import asyncio
import json
import tempfile
from collections import Counter
from pathlib import Path

import app.prediction.prediction_paper_automation as automation_module
from app.prediction.paper_engine import PredictionPaperJournal
from app.prediction.prediction_paper_automation import (
    PredictionAutomationConfig,
    PredictionPaperAutomation,
)


async def main() -> int:
    with tempfile.TemporaryDirectory(prefix="atlas-prediction-live-") as tmp:
        root = Path(tmp)
        journal = PredictionPaperJournal(
            journal_path=root / "paper_trades.jsonl",
            candidate_path=root / "paper_candidates.jsonl",
        )
        automation_module.prediction_paper_journal = journal
        service = PredictionPaperAutomation(
            config=PredictionAutomationConfig(
                discovery_limit=40,
                max_concurrency=4,
                orderbook_depth=20,
                history_minutes=180,
            )
        )
        state = await service.run_scan_once()
        status = service.status()
        candidates = journal._rows(journal.candidate_path)
        reason_counts = Counter(
            reason
            for row in candidates
            for reason in (row.get("rejection_reasons") or [])
        )
        payload = {
            "head_gate": "LIVE_PUBLIC_DATA_SCANNER_SMOKE",
            "state": state,
            "candidate_rows": len(candidates),
            "rejection_reason_counts": dict(sorted(reason_counts.items())),
            "candidate_samples": [
                {
                    "ticker": row.get("ticker"),
                    "side": row.get("side"),
                    "stage": row.get("evaluation_stage"),
                    "occurrence_datetime": row.get("occurrence_datetime"),
                    "rejection_reasons": row.get("rejection_reasons"),
                }
                for row in candidates[:6]
            ],
            "open_trade": journal.open_trade(),
            "automation": status,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))

        assert 0 < state["markets_discovered"] <= 40
        assert state["error_count"] == 0
        assert state["yes_evaluations"] == state["no_evaluations"]
        assert status["execution"] == "PAPER_ONLY"
        assert status["unattended_paper_open_enabled"] is False
        assert status["automatic_paper_position_opening"] is False
        assert status["live_execution"] is False
        assert status["live_capital_allowed"] is False
        assert status["automatic_real_money_execution"] is False
        assert journal.open_trade() is None
        assert len(candidates) >= (
            state["markets_prefilter_rejected"] * 2
            + state["markets_fully_evaluated"] * 2
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
