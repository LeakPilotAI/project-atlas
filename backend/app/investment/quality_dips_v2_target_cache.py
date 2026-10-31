"""Read-only analyst-target cache for Quality Dips V2 runtime normalization evidence."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from app.investment.storage import DATA_DIR, ensure_dirs
from app.investment.yfinance_client import YFinanceClient

CACHE_PATH = DATA_DIR / "quality_dips_v2_targets.json"
TTL = timedelta(hours=6)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _float(v: Any) -> float | None:
    try:
        x = float(v)
        return x if x > 0 and x == x else None
    except (TypeError, ValueError):
        return None


def _dt(v: Any) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)
    except Exception:
        return None


class QualityDipsV2TargetCache:
    def __init__(self) -> None:
        self.client = YFinanceClient(min_interval_sec=0.05, timeout_sec=8.0)
        self._rows: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._refresh_task: asyncio.Task | None = None
        self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(CACHE_PATH.read_text(encoding="utf-8")) if CACHE_PATH.exists() else {}
            rows = raw.get("symbols") if isinstance(raw, dict) else {}
            if isinstance(rows, dict):
                self._rows = {str(k).upper(): dict(v) for k, v in rows.items() if isinstance(v, dict)}
        except Exception:
            self._rows = {}

    def _save(self) -> None:
        ensure_dirs()
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"symbols": self._rows}, indent=2), encoding="utf-8")
        tmp.replace(CACHE_PATH)

    def get(self, symbol: str) -> dict[str, Any]:
        return dict(self._rows.get(str(symbol).upper()) or {})

    def sources(self, symbol: str) -> list[dict[str, Any]]:
        row = self.get(symbol)
        values = row.get("targets") if isinstance(row.get("targets"), dict) else {}
        as_of = row.get("as_of")
        out = []
        for key, note in (("low", "analyst target low"), ("mean", "analyst target mean"), ("high", "analyst target high")):
            value = _float(values.get(key))
            if value is not None:
                out.append({"value": value, "provenance": "ANALYST_CONSENSUS", "as_of": as_of, "confidence": "EXTERNAL_CONSENSUS", "note": note + "; provider-supplied, not an Atlas guarantee"})
        return out

    def _fresh(self, symbol: str) -> bool:
        fetched = _dt(self.get(symbol).get("fetched_at"))
        return fetched is not None and _now() - fetched <= TTL

    def schedule_refresh(self, symbols: Iterable[str]) -> bool:
        """Schedule refresh without blocking an API request. One refresh may run at a time."""
        clean = tuple(sorted({str(s or "").upper().strip() for s in symbols if str(s or "").strip()}))
        if not clean or all(self._fresh(s) for s in clean):
            return False
        if self._refresh_task is not None and not self._refresh_task.done():
            return False
        loop = asyncio.get_running_loop()
        self._refresh_task = loop.create_task(self.refresh_many(clean), name="quality-dips-v2-target-refresh")
        self._refresh_task.add_done_callback(self._consume_refresh_result)
        return True

    @staticmethod
    def _consume_refresh_result(task: asyncio.Task) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            # Provider/cache refresh must never take the Quality Dips API down.
            pass

    async def refresh_many(self, symbols: Iterable[str]) -> None:
        clean = sorted({str(s or "").upper().strip() for s in symbols if str(s or "").strip()})
        needed = [s for s in clean if not self._fresh(s)]
        if not needed:
            return
        sem = asyncio.Semaphore(5)

        async def one(symbol: str) -> tuple[str, dict[str, Any] | None]:
            async with sem:
                try:
                    info = await self.client.info(symbol)
                    targets = {"low": _float(info.get("targetLowPrice")), "mean": _float(info.get("targetMeanPrice")), "high": _float(info.get("targetHighPrice"))}
                    valid = [v for v in targets.values() if v is not None]
                    return symbol, {"targets": targets, "as_of": _now().isoformat(), "fetched_at": _now().isoformat(), "source": "yfinance_info", "complete": len(valid) >= 3}
                except Exception:
                    # Keep the last-known-good row. A transient provider failure must
                    # not erase usable normalization evidence from the cache.
                    return symbol, None

        results = await asyncio.gather(*(one(s) for s in needed))
        async with self._lock:
            changed = False
            for symbol, row in results:
                if row is not None:
                    self._rows[symbol] = row
                    changed = True
            if changed:
                self._save()


quality_dips_v2_target_cache = QualityDipsV2TargetCache()
