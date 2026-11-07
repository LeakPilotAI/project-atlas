"""Read-only accounting audit for retained pending PAPER identities."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from scripts.diagnostics.reconcile_pending_paper_history import _snapshot, reconcile


def _time(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else None
    except ValueError:
        return None


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def audit(pending_path: Path, paper_path: Path):
    baseline = reconcile(pending_path, paper_path)
    _, rows = _snapshot(paper_path)
    affected = {case["setup_instance_id"] for case in baseline["cases"]}
    trades = defaultdict(list)
    linked = defaultdict(set)
    for line, row in rows:
        trade_id = row.get("trade_id")
        if not isinstance(trade_id, str) or not trade_id:
            continue
        trades[trade_id].append((line, row))
        features = row.get("features")
        identity = features.get("setup_instance_id") if isinstance(features, dict) else None
        if identity in affected:
            linked[identity].add(trade_id)
    # An identity on any trade row is relevant even if its open is absent.
    results = []
    for case in baseline["cases"]:
        identity = case["setup_instance_id"]
        findings = list(case["missing_or_ambiguous"])
        trade_results = []
        for trade_id in sorted(linked[identity]):
            events = trades[trade_id]
            opens = [(n, r) for n, r in events if r.get("event") == "open"]
            closes = [(n, r) for n, r in events if r.get("event") == "close"]
            marks = [(n, r) for n, r in events if r.get("event") == "mark"]
            issues = []
            if len(opens) != 1:
                issues.append("expected exactly one linked open")
            if len(closes) > 1:
                issues.append("duplicate close")
            if not opens and (marks or closes):
                issues.append("orphan mark or close")
            if opens and closes and closes[0][0] <= opens[0][0]:
                issues.append("close precedes open in journal")
            if opens and closes and any(not opens[0][0] < n < closes[0][0] for n, _ in marks):
                issues.append("mark outside open-close journal interval")
            for number, row in opens + closes:
                if row.get("trade_type") != "PAPER" or row.get("counts_for_live") is True:
                    issues.append(f"authority contradiction at line {number}")
            if opens and opens[0][1].get("source") != "perp_manual_auto":
                issues.append("linked open source mismatch")
            if any(_time(row.get("exit_timestamp" if row.get("event") == "close" else
                                 "entry_timestamp" if row.get("event") == "open" else "timestamp")) is None
                   for _, row in opens + closes + marks):
                issues.append("missing or invalid lifecycle timestamp")
            if opens and closes:
                start = _time(opens[0][1].get("entry_timestamp"))
                end = _time(closes[0][1].get("exit_timestamp"))
                if start and end and end < start:
                    issues.append("close timestamp precedes open")
            recorded = closes[0][1].get("net_pnl_r") if len(closes) == 1 else None
            independently_computed = None
            if len(opens) == len(closes) == 1:
                open_row, close_row = opens[0][1], closes[0][1]
                entry, exit_price, risk = (open_row.get("actual_entry_price"),
                                           close_row.get("actual_exit_price"), open_row.get("risk_price"))
                fees, slip = open_row.get("fees_bps"), open_row.get("slippage_bps")
                if all(_number(x) for x in (entry, exit_price, risk, fees, slip, recorded)) and risk > 0:
                    side = open_row.get("side")
                    if side in {"LONG", "SHORT"}:
                        gross = (exit_price - entry) / risk if side == "LONG" else (entry - exit_price) / risk
                        independently_computed = round(gross - (fees + slip) / 10000 * 2 * entry / risk, 4)
                        if close_row.get("result") == "SESSION_ROLL":
                            independently_computed = 0.0
                        if abs(independently_computed - recorded) > 0.0002:
                            issues.append("recorded net R differs from documented formula")
                    else:
                        issues.append("missing or invalid side")
                else:
                    issues.append("insufficient fields to recompute net R")
            if closes and not _number(recorded):
                issues.append("recorded close net R missing or invalid")
            if issues:
                findings.extend(f"{trade_id}: {issue}" for issue in issues)
            trade_results.append({"trade_id": trade_id, "open_lines": [n for n, _ in opens],
                                  "mark_lines": [n for n, _ in marks], "close_lines": [n for n, _ in closes],
                                  "recorded_closed_net_r": recorded if _number(recorded) else None,
                                  "recomputed_closed_net_r": independently_computed,
                                  "last_recorded_mark_unrealized_r": marks[-1][1].get("unrealized_r") if marks else None,
                                  "current_unrealized_r": None,
                                  "issues": issues})
        if case["pending_fill_count"] != sum(bool(t["open_lines"]) for t in trade_results):
            findings.append("pending fill/open count mismatch")
        results.append({"setup_instance_id": identity, "identity_sha256": case["identity_sha256"],
                        "pending_event_lines": [r["line"] for r in case["pending_events"]],
                        "rearm_count": len(case["rearm_links"]), "pending_fill_count": case["pending_fill_count"],
                        "trades": trade_results, "findings": findings,
                        "accounting_status": "INCOMPLETE" if findings else "LOCALLY_CONSISTENT_UNAUTHENTICATED",
                        "compatibility": "HISTORICAL_EXCEPTION_REQUIRED_NOT_GRANTED"})
    # Recheck source bytes after all processing, including the pending file.
    for path, expected in ((pending_path, baseline["pending"]["sha256"]),
                           (paper_path, baseline["paper"]["sha256"])):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("source journal changed during accounting audit")
    return {"schema": "ATLAS_HISTORICAL_PAPER_ACCOUNTING_AUDIT_V1", "sources":
            {"pending": baseline["pending"], "paper": baseline["paper"]},
            "affected_identities": len(results), "cases": results,
            "locally_consistent": sum(c["accounting_status"] == "LOCALLY_CONSISTENT_UNAUTHENTICATED" for c in results),
            "production_authorized": False, "historical_exception_applied": False,
            "limitations": ["Sequential journals are not an independently authenticated atomic snapshot",
                            "Recorded marks are historical, not a live position valuation",
                            "Close R recomputation follows current journal formula; older code provenance unverified"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pending", required=True, type=Path)
    parser.add_argument("--paper", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.pending, args.paper)
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps({"affected_identities": result["affected_identities"],
                      "locally_consistent": result["locally_consistent"]}))


if __name__ == "__main__":
    main()
