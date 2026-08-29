"""Yahoo/provider reliability. Separate from investment observations. No scoring."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from app.investment.storage import PROVIDER_HEALTH_PATH, PROVIDER_HEALTH_LOG, ensure_dirs

COUNTERS = (
    "requests",
    "successes",
    "timeouts",
    "http_401",
    "http_429",
    "empty",
    "missing_ticker",
    "other",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ProviderHealthBook:
    source: str = "yfinance"
    requests: int = 0
    successes: int = 0
    timeouts: int = 0
    http_401: int = 0
    http_429: int = 0
    empty: int = 0
    missing_ticker: int = 0
    other: int = 0
    last_error: str = ""
    last_at: Optional[str] = None
    path: Optional[Path] = None
    log_path: Optional[Path] = None
    persist: bool = False

    def record(self, code: str, *, success: bool, message: str = "") -> None:
        self.requests += 1
        self.last_at = _now().isoformat()
        c = (code or "").upper()
        if success:
            self.successes += 1
        elif c in ("TIMEOUT",):
            self.timeouts += 1
            self.last_error = message or c
        elif c in ("HTTP_401", "401"):
            self.http_401 += 1
            self.last_error = message or c
        elif c in ("RATE_LIMIT", "HTTP_429", "429"):
            self.http_429 += 1
            self.last_error = message or c
        elif c in ("EMPTY",):
            self.empty += 1
            self.last_error = message or c
        elif c in ("MISSING_TICKER",):
            self.missing_ticker += 1
            self.last_error = message or c
        else:
            self.other += 1
            self.last_error = message or c
        if self.persist:
            self.save()
            self._log(code, success, message)

    def rates(self) -> Dict[str, Optional[float]]:
        n = self.requests
        if n <= 0:
            return {"success_rate": None, "failure_rate": None}
        ok = self.successes
        return {
            "success_rate": ok / n,
            "failure_rate": (n - ok) / n,
            "timeout_rate": self.timeouts / n,
            "http_401_rate": self.http_401 / n,
            "http_429_rate": self.http_429 / n,
        }

    def status_label(self) -> str:
        if self.requests <= 0:
            return "UNKNOWN"
        if self.http_429 > 0 or self.http_401 > self.successes:
            return "DEGRADED"
        if self.successes == 0:
            return "DOWN"
        ratio = self.successes / max(1, self.requests)
        if ratio >= 0.85:
            return "OK"
        if ratio >= 0.40:
            return "DEGRADED"
        return "DOWN"

    def as_dict(self) -> Dict[str, object]:
        return {
            "source": self.source,
            "requests": self.requests,
            "successes": self.successes,
            "timeouts": self.timeouts,
            "http_401": self.http_401,
            "http_429": self.http_429,
            "empty": self.empty,
            "missing_ticker": self.missing_ticker,
            "other": self.other,
            "last_error": self.last_error,
            "last_at": self.last_at,
            "status": self.status_label(),
            **{k: v for k, v in self.rates().items()},
        }

    def save(self) -> None:
        if not self.path:
            return
        ensure_dirs()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.as_dict(), indent=2), encoding="utf-8")

    def _log(self, code: str, success: bool, message: str) -> None:
        if not self.log_path:
            return
        ensure_dirs()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "at": self.last_at,
            "source": self.source,
            "code": code,
            "success": success,
            "message": (message or "")[:200],
        }
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")

    @classmethod
    def load(cls, path: Optional[Path] = None, *, persist: bool = False) -> "ProviderHealthBook":
        p = path or PROVIDER_HEALTH_PATH
        book = cls(path=p, log_path=PROVIDER_HEALTH_LOG, persist=persist)
        if not p.exists():
            return book
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return book
        for k in COUNTERS:
            if k in data:
                setattr(book, k, int(data.get(k) or 0))
        book.last_error = str(data.get("last_error") or "")
        book.last_at = data.get("last_at")
        return book


_BOOK = ProviderHealthBook()


def get_provider_health() -> ProviderHealthBook:
    return _BOOK


def configure_provider_health(*, path: Optional[Path] = None, persist: bool = False) -> ProviderHealthBook:
    global _BOOK
    if persist:
        _BOOK = ProviderHealthBook.load(path or PROVIDER_HEALTH_PATH, persist=True)
    else:
        _BOOK = ProviderHealthBook(path=path, persist=False)
    return _BOOK


def record_provider_event(code: str, *, success: bool, message: str = "") -> None:
    get_provider_health().record(code, success=success, message=message)
