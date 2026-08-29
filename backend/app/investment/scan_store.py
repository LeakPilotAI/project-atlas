"""Append-only scan observations. Never overwrite. Never touch trading journals."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from app.investment.scan_models import ScanObservation, ScanReport
from app.investment.storage import OBSERVATIONS_PATH, SCAN_LOG_PATH, ensure_dirs


def append_observation(obs: ScanObservation, path: Optional[Path] = None) -> Path:
    ensure_dirs()
    p = path or OBSERVATIONS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obs.as_dict(), default=str) + "\n")
    return p


def load_observations(path: Optional[Path] = None) -> List[dict]:
    p = path or OBSERVATIONS_PATH
    if not p.exists():
        return []
    out: List[dict] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def append_scan_log(report: ScanReport, path: Optional[Path] = None) -> None:
    ensure_dirs()
    p = path or SCAN_LOG_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(report.as_dict(), default=str) + "\n")
