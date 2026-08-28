"""Append-only research records. Never overwrite. Never touch trading journals."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from app.investment.research_models import ResearchRecord
from app.investment.storage import OPPORTUNITIES_PATH, ensure_dirs


def append_research(record: ResearchRecord, path: Optional[Path] = None) -> Path:
    ensure_dirs()
    p = path or OPPORTUNITIES_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record.as_dict(), default=str) + "\n")
    return p


def load_research(path: Optional[Path] = None) -> List[dict]:
    p = path or OPPORTUNITIES_PATH
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
