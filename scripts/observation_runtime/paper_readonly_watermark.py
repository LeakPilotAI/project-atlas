"""Durable, data-only replay watermark for a future supervised PAPER reader.

Not an operator lease, financial journal, provider attestation, or fill permit.
A missing/corrupt file is refused after enrollment; never silently reset it.
"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
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



@contextmanager
def readonly_watermark_writer(path: Path):
    """Windows OS advisory lock held across the entire watermark session.

    The lock file is retained on disk so a second process cannot race a
    deleted-and-recreated lock path. Not an operator/financial writer lease.
    """
    import msvcrt
    if not isinstance(path, Path) or not path.parent.is_dir():
        raise ValueError("READONLY_WATERMARK_LOCK_PARENT_INVALID")
    lock_path = path.with_name(path.name + ".writer.lock")
    if lock_path.is_symlink():
        raise ValueError("READONLY_WATERMARK_LOCK_PATH_REFUSED")
    with lock_path.open("a+b") as handle:
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise ValueError("READONLY_WATERMARK_WRITER_ALREADY_OWNED") from exc
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)

def run_watermarked_readonly_paper_session(*, path: Path, symbol: str,
                                           enrolled: bool, ticks: int,
                                           clock, **dependencies) -> dict:
    """Connect the existing leased read-only session to a durable event cut.

    Caller must own the session's single-writer lock. An enrolled session
    cannot restart from a missing watermark; no synthetic fill is permitted.
    """
    from app.services.personal_paper_strategy_signal import run_bounded_readonly_paper_session
    if type(enrolled) is not bool or not enrolled:
        raise ValueError("READONLY_WATERMARK_ENROLLMENT_REQUIRED")
    if type(symbol) is not str or not symbol or "previous_provider_timestamp" in dependencies:
        raise ValueError("READONLY_WATERMARK_SESSION_IDENTITY_INVALID")
    with readonly_watermark_writer(path):
        previous = read_watermark(path, symbol=symbol)
        if previous is None:
            raise ValueError("READONLY_WATERMARK_ENROLLED_STATE_MISSING")
        # Persist after each accepted tick, not after a multi-tick batch.
        # A crash must not silently discard earlier processed observations.
        if type(ticks) is not int or not 1 <= ticks <= 30:
            raise ValueError("READONLY_WATERMARK_BOUNDED_TICKS_REQUIRED")
        records = []
        for _ in range(ticks):
            result = run_bounded_readonly_paper_session(
                ticks=1, clock=clock, symbol=symbol, previous_provider_timestamp=previous, **dependencies)
            if result.get("paper_fill_authorized") is not False or result.get("live_order_authorized") is not False:
                raise ValueError("READONLY_WATERMARK_UNEXPECTED_AUTHORITY")
            current = result["last_provider_timestamp"]
            advance_watermark(path, symbol=symbol, provider_timestamp=current)
            previous = current
            records.extend(result["ticks"])
    return strict(body({"schema": "ATLAS_WATERMARKED_READONLY_PAPER_SESSION_V1",
                        "completed": len(records), "ticks": records,
                        "last_provider_timestamp": previous,
                        "paper_fill_authorized": False, "live_order_authorized": False}))
