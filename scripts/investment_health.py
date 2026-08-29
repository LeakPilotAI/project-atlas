#!/usr/bin/env python3
"""Investment data health + dataset statistics. Not performance. Not /paper."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.investment.dataset import format_dataset_report  # noqa: E402
from app.investment.diagnostics import format_full_health, format_scanner_health  # noqa: E402
from app.investment.integrity import format_pit_audit  # noqa: E402
from app.investment.monitor import format_collection_monitor  # noqa: E402
from app.investment.quality import format_quality_breakdown  # noqa: E402
from app.investment.readiness import format_readiness  # noqa: E402
from app.investment.scan import investment_scanner  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Atlas investment data health (research-only)")
    p.add_argument("--dataset-only", action="store_true")
    p.add_argument("--cycle-only", action="store_true")
    p.add_argument("--readiness", action="store_true")
    p.add_argument("--quality", action="store_true")
    p.add_argument("--audit", action="store_true")
    p.add_argument("--monitor", action="store_true")
    args = p.parse_args()
    running = bool(investment_scanner.running)
    if args.dataset_only:
        print(format_dataset_report())
        return 0
    if args.cycle_only:
        print(format_scanner_health(running=running))
        return 0
    if args.readiness:
        print(format_readiness())
        return 0
    if args.quality:
        print(format_quality_breakdown())
        return 0
    if args.audit:
        print(format_pit_audit())
        return 0
    if args.monitor:
        print(format_collection_monitor())
        return 0
    print(format_full_health(running=running))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
