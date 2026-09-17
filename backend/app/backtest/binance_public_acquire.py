"""Acquire free public Binance USD-M futures klines for Atlas historical research.

No account, API key, AWS account, or paid service is required. Raw monthly ZIPs and
published CHECKSUM files are retained so later canonical manifests can preserve
source provenance. This module acquires candles only; it does NOT synthesize
Hyperliquid OI/rolling-volume context and cannot by itself make source_audit GREEN.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path

BASE_URL = "https://data.binance.vision/data/futures/um/monthly/klines"
SYMBOL_MAP = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT"}
INTERVALS = {"5m", "1h"}


def _date(value: str) -> date:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).date()


def _months(start_utc: str, end_utc: str) -> list[str]:
    start, end = _date(start_utc), _date(end_utc)
    if start >= end:
        raise ValueError("start must precede end")
    cur = date(start.year, start.month, 1)
    out: list[str] = []
    while cur < end:
        out.append(f"{cur:%Y-%m}")
        cur = date(cur.year + (cur.month == 12), 1 if cur.month == 12 else cur.month + 1, 1)
    return out


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class PublicKlineObject:
    symbol: str
    provider_symbol: str
    interval: str
    month: str
    url: str
    checksum_url: str
    local_zip: str
    local_checksum: str


def plan(*, start_utc: str, end_utc: str, raw_root: Path,
         symbols: tuple[str, ...] = ("BTC", "ETH", "SOL"),
         intervals: tuple[str, ...] = ("5m", "1h")) -> dict:
    bad_symbols = sorted(set(symbols) - set(SYMBOL_MAP))
    bad_intervals = sorted(set(intervals) - INTERVALS)
    if bad_symbols:
        raise ValueError(f"unsupported representative symbols: {', '.join(bad_symbols)}")
    if bad_intervals:
        raise ValueError(f"unsupported intervals: {', '.join(bad_intervals)}")
    objects: list[PublicKlineObject] = []
    for symbol in symbols:
        provider_symbol = SYMBOL_MAP[symbol]
        for interval in intervals:
            for month in _months(start_utc, end_utc):
                filename = f"{provider_symbol}-{interval}-{month}.zip"
                url = f"{BASE_URL}/{provider_symbol}/{interval}/{filename}"
                local_dir = Path(raw_root) / "binance_public" / provider_symbol / interval
                objects.append(PublicKlineObject(
                    symbol=symbol,
                    provider_symbol=provider_symbol,
                    interval=interval,
                    month=month,
                    url=url,
                    checksum_url=url + ".CHECKSUM",
                    local_zip=str(local_dir / filename),
                    local_checksum=str(local_dir / (filename + ".CHECKSUM")),
                ))
    return {
        "mode": "RESEARCH_ONLY_PUBLIC_CANDLE_ACQUISITION",
        "source": "binance:data.binance.vision:futures_um_monthly_klines",
        "start_utc": start_utc,
        "end_utc": end_utc,
        "symbols": list(symbols),
        "intervals": list(intervals),
        "authentication_required": False,
        "paid_service_required": False,
        "aws_required": False,
        "candles_only": True,
        "pit_oi_context_complete": False,
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
        "current_state_backfill_allowed": False,
        "objects": [asdict(x) for x in objects],
    }


def _download(url: str, path: Path, *, timeout: int = 20, attempts: int = 3) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response, tmp.open("wb") as fh:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    fh.write(chunk)
            tmp.replace(path)
            return
        except Exception as exc:
            last = exc
            tmp.unlink(missing_ok=True)
            if attempt < attempts:
                time.sleep(min(2 ** (attempt - 1), 4))
    assert last is not None
    raise last


def _published_sha256(checksum_path: Path) -> str:
    text = checksum_path.read_text(encoding="utf-8").strip()
    token = text.split()[0].lower() if text else ""
    if len(token) != 64 or any(c not in "0123456789abcdef" for c in token):
        raise RuntimeError(f"invalid published checksum: {checksum_path}")
    return token


def _verified_existing(zip_path: Path, checksum_path: Path) -> tuple[bool, str | None]:
    if not zip_path.exists() or not checksum_path.exists():
        return False, None
    try:
        published = _published_sha256(checksum_path)
        actual = _sha256(zip_path)
    except Exception:
        return False, None
    return published == actual, actual if published == actual else None


def acquire(payload: dict) -> dict:
    results = []
    total = len(payload["objects"])
    for index, obj in enumerate(payload["objects"], start=1):
        zip_path, checksum_path = Path(obj["local_zip"]), Path(obj["local_checksum"])
        verified, existing_sha = _verified_existing(zip_path, checksum_path)
        if verified:
            print(f"[{index}/{total}] {obj['provider_symbol']} {obj['interval']} {obj['month']} skip verified", flush=True)
            published = _published_sha256(checksum_path)
            actual = existing_sha or _sha256(zip_path)
        else:
            print(f"[{index}/{total}] {obj['provider_symbol']} {obj['interval']} {obj['month']} download", flush=True)
            try:
                _download(obj["checksum_url"], checksum_path)
                _download(obj["url"], zip_path)
            except urllib.error.HTTPError as exc:
                raise RuntimeError(f"public candle acquisition failed for {obj['provider_symbol']} {obj['interval']} {obj['month']}: HTTP {exc.code}") from exc
            except Exception as exc:
                raise RuntimeError(f"public candle acquisition failed for {obj['provider_symbol']} {obj['interval']} {obj['month']}: {type(exc).__name__}: {exc}") from exc
            published, actual = _published_sha256(checksum_path), _sha256(zip_path)
            if published != actual:
                raise RuntimeError(f"checksum mismatch for {zip_path}: published={published} actual={actual}")
        results.append({**obj, "bytes": zip_path.stat().st_size, "sha256": actual,
                        "published_sha256": published, "status": "ACQUIRED_CHECKSUM_VERIFIED"})
    return {**payload, "objects": results,
            "acquisition_status": "ACQUIRED_RAW_CANDLES_CHECKSUM_VERIFIED_CONTEXT_STILL_REQUIRED"}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Plan/acquire free public Binance USD-M futures candles")
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--raw-root", type=Path, default=Path("backend/data/research/raw/historical"))
    p.add_argument("--manifest", type=Path, default=Path("backend/data/research/historical/binance-public-candles.json"))
    p.add_argument("--symbols", nargs="+", default=["BTC", "ETH", "SOL"])
    p.add_argument("--intervals", nargs="+", default=["5m", "1h"])
    p.add_argument("--execute", action="store_true")
    a = p.parse_args(argv)
    payload = plan(start_utc=a.start, end_utc=a.end, raw_root=a.raw_root,
                   symbols=tuple(x.upper() for x in a.symbols), intervals=tuple(a.intervals))
    payload = acquire(payload) if a.execute else {**payload, "acquisition_status": "PLANNED_NOT_DOWNLOADED"}
    a.manifest.parent.mkdir(parents=True, exist_ok=True)
    a.manifest.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"candle_manifest={a.manifest}")
    print(f"objects={len(payload['objects'])} status={payload['acquisition_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
