"""Reproducible, read-only Ruff inventory; writes fresh audit outputs, never fixes."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


def relative_name(filename: str) -> str:
    name = filename.replace("\\", "/")
    for prefix in ("backend/", "scripts/", "tests/"):
        marker = "/" + prefix
        if marker in name:
            return prefix + name.split(marker, 1)[1]
    return name


def diagnostic_key(row: dict) -> tuple:
    return relative_name(row["filename"]), row["code"], row["message"]


def inventory(root: Path, output: Path, head: Path, previous: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    targets = [root / "backend/app", root / "scripts", root / "tests"]
    command = [sys.executable, "-m", "ruff", "check", *map(str, targets),
               "--output-format", "json"]
    run = subprocess.run(command, capture_output=True, encoding="utf-8", check=False)
    if run.returncode not in (0, 1):
        raise RuntimeError("Ruff failed to produce an inventory")
    rows = json.loads(run.stdout)
    (output / "raw.json").write_text(run.stdout, encoding="utf-8")
    head_counts = Counter(diagnostic_key(row) for row in json.loads(head.read_text(encoding="utf-8-sig")))
    previous_counts = Counter(diagnostic_key(row) for row in json.loads(previous.read_text(encoding="utf-8-sig")))
    baseline_previous = previous_counts.copy()
    candidates = Counter(diagnostic_key(row) for row in rows)
    enriched = []
    for row in sorted(rows, key=lambda item: (*diagnostic_key(item), item["location"]["row"])):
        key = diagnostic_key(row)
        prior = previous_counts[key] > 0
        if prior:
            previous_counts[key] -= 1
        ancestry = "HEAD_inherited" if head_counts[key] > 0 else "pre_S_inherited" if prior else "new_S"
        if head_counts[key] > 0:
            head_counts[key] -= 1
        code = row["code"]
        category = ("style_baseline_candidate" if code.startswith(("UP", "W", "Q")) or code in {"I001", "E501"}
                    else "security_policy_review" if code.startswith("BLE") or (code.startswith("S") and code[1:2].isdigit())
                    else "correctness_review")
        enriched.append({"path": key[0], "rule": code, "message": row["message"],
                         "row": row["location"]["row"], "column": row["location"]["column"],
                         "ancestry": ancestry, "new_since_R": not prior,
                         "review_category": category, "disposition": "UNADJUDICATED",
                         "approval_needed_for_baseline": True})
    (output / "findings.json").write_text(json.dumps(enriched, indent=2), encoding="utf-8")
    with (output / "by-file-rule.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["file", "rule", "count"])
        for (name, code), count in sorted(Counter((row["path"], row["rule"]) for row in enriched).items()):
            writer.writerow([name, code, count])
    settings = subprocess.run([sys.executable, "-m", "ruff", "check", "--show-settings",
                               str(root / "backend/app/main.py")], capture_output=True,
                              encoding="utf-8", check=True).stdout
    (output / "settings.txt").write_text(settings, encoding="utf-8")
    summary = {"count": len(rows), "command": command,
               "version": subprocess.check_output([sys.executable, "-m", "ruff", "--version"], encoding="utf-8").strip(),
               "by_rule": dict(sorted(Counter(row["rule"] for row in enriched).items())),
               "by_file": dict(sorted(Counter(row["path"] for row in enriched).items())),
               "ancestry": dict(Counter(row["ancestry"] for row in enriched)),
               "review_categories": dict(Counter(row["review_category"] for row in enriched)),
               "new_since_R": sum(row["new_since_R"] for row in enriched),
               "resolved_since_R": sum((baseline_previous - candidates).values()),
               "match_method": "file/rule/message multiset, not proof of individual-line ancestry",
               "baseline_approved": False, "release_quality_gate": "BLOCKED"}
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--head-baseline", required=True, type=Path)
    parser.add_argument("--previous-baseline", required=True, type=Path)
    args = parser.parse_args()
    summary = inventory(args.root.resolve(), args.output, args.head_baseline, args.previous_baseline)
    print(json.dumps({"count": summary["count"], "new_since_R": summary["new_since_R"]}))
