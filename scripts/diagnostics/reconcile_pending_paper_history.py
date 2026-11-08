"""Read-only, exact-identity reconciliation of retained PAPER JSONL evidence.

Writes a new diagnostic only. It never repairs, replays, or opens a PAPER order.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _refuse_constant(value):
    raise ValueError(f"nonfinite JSON value: {value}")


def _snapshot(path: Path):
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"ordinary existing journal required: {path}")
    before = path.stat()
    raw = path.read_bytes()
    if not raw or not raw.endswith(b"\n") or len(raw) != before.st_size:
        raise ValueError(f"complete stable journal required: {path}")
    rows = []
    for line_number, line in enumerate(raw.splitlines(), 1):
        if len(line) > 1024 * 1024:
            raise ValueError(f"oversized JSONL row {line_number}: {path}")
        row = json.loads(line, object_pairs_hook=_unique, parse_constant=_refuse_constant)
        if type(row) is not dict:
            raise ValueError(f"object JSONL row required at {line_number}: {path}")
        rows.append((line_number, row))
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        raise ValueError(f"journal changed during read: {path}")
    return raw, rows


def reconcile(pending_path: Path, paper_path: Path):
    pending_raw, pending_rows = _snapshot(pending_path)
    paper_raw, paper_rows = _snapshot(paper_path)
    terminal = {}
    active = set()
    repeated_active = set()
    pending_by_identity = defaultdict(list)
    violations = defaultdict(list)
    for line, row in pending_rows:
        identity = row.get("setup_instance_id")
        event = row.get("event")
        if type(identity) is not str or not identity or event not in {"armed", "filled", "cancelled"}:
            raise ValueError(f"invalid pending identity/event at line {line}")
        item = {"line": line, "event": event, "timestamp": row.get("timestamp"),
                "reason": row.get("reason"), "symbol": row.get("symbol"),
                "side": row.get("side"), "setup_key": row.get("setup_key"),
                "source": row.get("source"), "strategy": row.get("strategy")}
        pending_by_identity[identity].append(item)
        if event == "armed" and identity in terminal:
            violations[identity].append({"rearm_line": line, "prior_terminal": terminal[identity]})
        if event == "armed" and identity in active:
            repeated_active.add(identity)
        if event == "armed":
            active.add(identity)
        if event in {"filled", "cancelled"}:
            active.discard(identity)
            terminal[identity] = {"line": line, "event": event, "timestamp": row.get("timestamp"),
                                  "reason": row.get("reason")}

    paper_by_identity = defaultdict(list)
    trade_identity = {}
    for line, row in paper_rows:
        event = row.get("event")
        features = row.get("features") if type(row.get("features")) is dict else {}
        identity = features.get("setup_instance_id")
        trade_id = row.get("trade_id")
        if event == "open" and row.get("source") == "perp_manual_auto" and type(identity) is str and identity:
            if trade_id in trade_identity and trade_identity[trade_id] != identity:
                raise ValueError(f"trade identity contradiction at PAPER line {line}")
            trade_identity[trade_id] = identity
        if not identity and trade_id in trade_identity:
            identity = trade_identity[trade_id]
        if type(identity) is str and identity in violations:
            paper_by_identity[identity].append({"line": line, "event": event,
                "trade_id": trade_id, "timestamp": row.get("exit_timestamp") if event == "close" else
                (row.get("timestamp") or row.get("entry_timestamp")),
                "source": row.get("source"), "trade_type": row.get("trade_type"),
                "status": row.get("status"), "counts_for_live": row.get("counts_for_live"),
                "entry_price": row.get("actual_entry_price") if event in {"open", "close"} else None,
                "exit_price": row.get("actual_exit_price") if event == "close" else None,
                "fees_bps": row.get("fees_bps") if event in {"open", "close"} else None,
                "slippage_bps": row.get("slippage_bps") if event in {"open", "close"} else None,
                "gross_pnl_r": row.get("gross_pnl_r") if event == "close" else None,
                "net_pnl_r": row.get("net_pnl_r") if event == "close" else None})

    cases = []
    for identity in sorted(violations):
        events = pending_by_identity[identity]
        related = paper_by_identity[identity]
        opens = [row for row in related if row["event"] == "open" and row["source"] == "perp_manual_auto"]
        closes = [row for row in related if row["event"] == "close"]
        fills = [row for row in events if row["event"] == "filled"]
        duplicate_opens = len(opens) > 1 or len({row["trade_id"] for row in opens}) != len(opens)
        missing = []
        if fills and not opens:
            missing.append("pending fill has no linked PAPER open")
        if opens and not fills:
            missing.append("PAPER open has no pending fill")
        if len(closes) > len(opens):
            missing.append("more linked closes than opens")
        if any(row["timestamp"] is None for row in events):
            missing.append("pending event timestamp missing")
        try:
            pending_times = [datetime.fromisoformat(row["timestamp"]) for row in events]
            if any(value.tzinfo is None for value in pending_times) or pending_times != sorted(pending_times):
                missing.append("pending event chronology unavailable or out of order")
        except (TypeError, ValueError):
            missing.append("pending event chronology unavailable or out of order")
        if any(row["trade_type"] != "PAPER" or row["counts_for_live"] is True for row in opens + closes):
            missing.append("linked PAPER authority/type evidence contradictory")
        open_ids = {row["trade_id"] for row in opens}
        if any(row["trade_id"] not in open_ids for row in closes):
            missing.append("linked close lacks matching open identity")
        if any(row["trade_id"] is None for row in opens + closes):
            missing.append("linked trade identity missing")
        if identity in repeated_active:
            missing.append("duplicate arm before terminal event")
        if any(row["net_pnl_r"] is None for row in closes):
            missing.append("linked close accounting value missing")
        if duplicate_opens or missing:
            contradictory = duplicate_opens or len(closes) > len(opens) or any(
                text in missing for text in ("linked PAPER authority/type evidence contradictory",
                                         "linked close lacks matching open identity",
                                         "pending event chronology unavailable or out of order",
                                         "duplicate arm before terminal event"))
            classification = "CONTRADICTORY EVIDENCE" if contradictory else "INSUFFICIENT EVIDENCE"
        else:
            classification = "HISTORICAL EXCEPTION REQUIRED"
        cases.append({"setup_instance_id": identity, "identity_sha256": hashlib.sha256(identity.encode()).hexdigest(),
                      "pending_events": events, "rearm_links": violations[identity],
                      "paper_events": related, "paper_open_count": len(opens), "paper_close_count": len(closes),
                      "pending_fill_count": len(fills), "missing_or_ambiguous": missing,
                      "classification": classification,
                      "reason": "Current terminal-identity contract refuses historical rearm; no exception was applied"})

    # The source files are not locked against external writers. Verify again
    # before publishing a point-in-time diagnostic; do not claim atomicity.
    if hashlib.sha256(pending_path.read_bytes()).digest() != hashlib.sha256(pending_raw).digest():
        raise ValueError("pending journal changed before diagnostic publication")
    if hashlib.sha256(paper_path.read_bytes()).digest() != hashlib.sha256(paper_raw).digest():
        raise ValueError("PAPER journal changed before diagnostic publication")
    return {"schema": "ATLAS_READ_ONLY_HISTORICAL_PAPER_RECONCILIATION_V1",
            "pending": {"path": str(pending_path), "sha256": hashlib.sha256(pending_raw).hexdigest(),
                        "bytes": len(pending_raw), "rows": len(pending_rows)},
            "paper": {"path": str(paper_path), "sha256": hashlib.sha256(paper_raw).hexdigest(),
                      "bytes": len(paper_raw), "rows": len(paper_rows)},
            "violating_rearm_events": sum(map(len, violations.values())),
            "affected_identities": len(cases),
            "classifications": dict(Counter(case["classification"] for case in cases)),
            "cases": cases, "journals_modified": False,
            "historical_exception_applied": False, "production_authorized": False,
            "limitations": ["Two files captured sequentially, not atomically",
                            "No independent external writer exclusion or historical completeness proof",
                            "Linkage relies on recorded setup_instance_id and trade_id fields",
                            "Classification does not authorize migration, replay, PAPER action or startup"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pending", type=Path, required=True)
    parser.add_argument("--paper", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = reconcile(args.pending, args.paper)
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    print(json.dumps({"output": str(args.output), "affected_identities": result["affected_identities"],
                      "violating_rearm_events": result["violating_rearm_events"],
                      "classifications": result["classifications"]}))


if __name__ == "__main__":
    main()
