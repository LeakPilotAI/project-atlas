"""Runtime hardening discovered by the multi-hour Atlas soak test.

This module is intentionally defensive. It does not alter strategy thresholds or
place orders. It hardens Hyperliquid transport retries, makes manual-perp state
fail closed on refresh failure, and prevents malformed journal bytes from taking
down read/reconcile paths.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from types import MethodType
from typing import Any

import httpx


def safe_iter_jsonl(path: Path) -> list[dict[str, Any]]:
    """Best-effort JSONL reader that never raises for bad bytes/truncated rows."""
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_no, line in enumerate(handle, start=1):
                raw = line.strip()
                if not raw:
                    continue
                try:
                    row = json.loads(raw)
                except Exception:
                    rows.append({"event": "_malformed", "line": line_no, "raw": raw[:200]})
                    continue
                if isinstance(row, dict):
                    rows.append(row)
                else:
                    rows.append({"event": "_malformed", "line": line_no, "raw": raw[:200]})
    except OSError as exc:
        rows.append({"event": "_malformed", "line": 0, "raw": f"journal read error: {type(exc).__name__}: {exc}"[:200]})
    return rows


def harden_adapter(adapter: Any) -> Any:
    """Install bounded retries on the live Hyperliquid info POST path."""
    if getattr(adapter, "_atlas_runtime_hardened", False):
        return adapter
    original_post = adapter._post

    async def resilient_post(self, body: dict[str, Any]) -> Any:
        last_exc: Exception | None = None
        for attempt in range(1, 4):
            try:
                result = await original_post(body)
                self._atlas_last_rest_success = datetime.now(timezone.utc).isoformat()
                self._atlas_consecutive_rest_failures = 0
                return result
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                status = getattr(exc.response, "status_code", 0) or 0
                if status < 500:
                    raise
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
            self._atlas_consecutive_rest_failures = int(getattr(self, "_atlas_consecutive_rest_failures", 0)) + 1
            if attempt < 3:
                await asyncio.sleep(0.4 * (2 ** (attempt - 1)))
        assert last_exc is not None
        raise last_exc

    adapter._post = MethodType(resilient_post, adapter)
    adapter._atlas_runtime_hardened = True
    adapter._atlas_last_rest_success = None
    adapter._atlas_consecutive_rest_failures = 0
    return adapter


def harden_manual_service(service: Any) -> Any:
    """On a complete market refresh failure, immediately stale/lock all setups."""
    if getattr(service, "_atlas_runtime_hardened", False):
        return service
    original_refresh = service.refresh

    async def resilient_refresh(*args, **kwargs):
        try:
            result = await original_refresh(*args, **kwargs)
            service.last_snapshot["data_status"] = "FRESH"
            service.last_snapshot["data_error"] = None
            service.last_snapshot["stale_since"] = None
            return result
        except Exception as exc:
            now = datetime.now(timezone.utc).isoformat()
            for setup in service.last_snapshot.get("setups") or []:
                setup["discovery_stale"] = True
                setup["state"] = "WAIT"
                setup["alert_eligible"] = False
                setup["alert_reason"] = "market data refresh failed; setup locked"
                setup["next_action"] = "Market data is stale. Do not place, move, chase, or auto-paper a new entry."
            service.last_snapshot["alert_candidates"] = []
            service.last_snapshot["data_status"] = "STALE"
            service.last_snapshot["data_error"] = f"{type(exc).__name__}: {str(exc)[:180]}"
            service.last_snapshot["stale_since"] = service.last_snapshot.get("stale_since") or now
            try:
                service._persist_state()
            except Exception:
                pass
            raise

    service.refresh = resilient_refresh
    service._atlas_runtime_hardened = True
    return service


def install_runtime_hardening(adapter: Any) -> None:
    """Install all soak-derived reliability protections exactly once."""
    harden_adapter(adapter)

    try:
        from app.services.perp_manual_service import perp_manual_service
        harden_manual_service(perp_manual_service)
    except Exception:
        pass

    try:
        from app.services import paper_journal as paper_journal_module
        paper_journal_module.iter_jsonl = safe_iter_jsonl
    except Exception:
        pass
