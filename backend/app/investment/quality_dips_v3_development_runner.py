"""Local runner for Quality Dips V3 DEVELOPMENT evidence.

Reads the operator's local investment observations, emits a deterministic JSON report,
and never mutates V3 thresholds or evaluates HOLDOUT for tuning.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.investment.quality_dips_v3_development import build_development_report
from app.investment.quality_dips_v3_pit_store import load_v3_pit_rows
from app.investment.storage import DATA_DIR, ensure_dirs

REPORT_PATH = DATA_DIR / "quality_dips_v3_development_report.json"


def run_development_report(output_path: Path = REPORT_PATH) -> dict:
    rows = load_v3_pit_rows()
    report = build_development_report(rows)
    ensure_dirs()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(output_path)
    return report


if __name__ == "__main__":
    print(json.dumps(run_development_report(), indent=2, sort_keys=True))
