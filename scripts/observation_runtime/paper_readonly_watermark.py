"""Durable, data-only replay watermark for a future supervised PAPER reader.

Not an operator lease, financial journal, provider attestation, or fill permit.
A missing/corrupt file is refused after enrollment; never silently reset it.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from app.services.personal_paper_observations import _aware
from app.services.paper_financial_replay import body, strict

SCHEMA = "ATLAS_READONLY_IEX_WATERMARK_V1"


def read_watermark(path: Path, *, symbol: str) -> str | None:
    if not isinstance(path, Path) or type(symbol) is not str or not symbol:
        raise ValueError("READONLY_WATERMARK_INPUT_INVALID")
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise ValueError("READONLY_WATERMARK_STORAGE_REFUSED")
    try:
        raw = path.read_bytes()
        if len(raw) > 4096:
            raise ValueError("READONLY_WATERMARK_TOO_LARGE")
        packet = strict(raw.decode("utf-8"))
        if (type(packet) is not dict or set(packet) != {"schema", "symbol", "provider_timestamp",
                                                    "paper_fill_authorized", "live_order_authorized"}
                or packet["schema"] != SCHEMA or packet["symbol"] != symbol
                or packet["paper_fill_authorized"] is not False
                or packet["live_order_authorized"] is not False):
            raise ValueError("READONLY_WATERMARK_CONTENT_REFUSED")
        stamp = _aware(packet["provider_timestamp"], "stored IEX event")
        return stamp.isoformat()
    except (OSError, UnicodeError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("READONLY_WATERMARK_STORAGE_REFUSED") from exc


def advance_watermark(path: Path, *, symbol: str, provider_timestamp: str) -> dict:
    """Atomic replacement of diagnostic watermark only, never financial state.

    The caller owns single-writer exclusion; this helper cannot provide it.
    """
    if not isinstance(path, Path) or type(symbol) is not str or not symbol:
        raise ValueError("READONLY_WATERMARK_INPUT_INVALID")
    stamp = _aware(provider_timestamp, "new IEX event")
    old = read_watermark(path, symbol=symbol)
    if old is not None and stamp <= _aware(old, "stored IEX event"):
        raise ValueError("READONLY_WATERMARK_REPLAY_REFUSED")
    if not path.parent.is_dir() or path.is_symlink():
        raise ValueError("READONLY_WATERMARK_PARENT_REFUSED")
    packet = {"schema": SCHEMA, "symbol": symbol, "provider_timestamp": stamp.isoformat(),
              "paper_fill_authorized": False, "live_order_authorized": False}
    temp = path.with_name(path.name + ".pending")
    try:
        with temp.open("x", encoding="utf-8") as handle:
            handle.write(body(packet) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()
    return packet
