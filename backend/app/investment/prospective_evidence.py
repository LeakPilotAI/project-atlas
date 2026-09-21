"""Append-only prospective research snapshots, isolated from legacy history."""

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
from threading import RLock

from app.investment.storage import DATA_DIR

OBSERVATIONS = DATA_DIR / "prospective_v3_observations.jsonl"
EVIDENCE_CLASSES = frozenset(
    {
        "HISTORICAL_IMMUTABLE",
        "FORWARD_COLLECTION",
        "DEVELOPMENT",
        "HOLDOUT",
        "PAPER",
        "TEST",
        "DIAGNOSTIC",
    }
)
POLICY_VERSION = "quality-dips-v3-mos-15-20-25-30-v1"
EXECUTION_VERSION = "investment-forward-observation-v1-no-assumed-fill"
_lock = RLock()


def read_records(path):
    if not Path(path).exists():
        return []
    with _lock:
        with Path(path).open(encoding="utf-8") as stream:
            # Avoid observing an in-process append before its complete line flushes.
            # Corrupt durable evidence fails visibly, rather than disappearing.
            return [json.loads(line) for line in stream if line.strip()]


def append_record(path, row):
    path = Path(path)
    payload = json.dumps(row, sort_keys=True, default=str, allow_nan=False)
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(payload + "\n")
            stream.flush()
            os.fsync(stream.fileno())


def _eligible_source(source, now):
    if str(source.get("evidence_class") or "").upper() in {"TEST", "DIAGNOSTIC"}:
        return False
    try:
        timestamp = datetime.fromisoformat(
            str(source.get("timestamp")).replace("Z", "+00:00")
        )
        if timestamp.tzinfo is None or timestamp > now:
            return False
        price = float(source.get("price"))
        return math.isfinite(price) and price > 0
    except (ValueError, TypeError):
        return False


def collect_board(board, research, path=OBSERVATIONS):
    """One first-seen snapshot per UTC day/symbol/policy, including blocked WATCH.

    Clock is taken here, never supplied by a backfill caller. Old source evidence
    is explicitly timestamped; snapshot date never claims a historical decision.
    """
    now = datetime.now(timezone.utc)
    latest = {}
    for source in research:
        symbol = str(source.get("symbol") or "").strip().upper()
        if symbol:
            if symbol not in latest or str(source.get("timestamp") or "") > str(
                latest[symbol].get("timestamp") or ""
            ):
                latest[symbol] = source
    with _lock:
        existing = {row["observation_id"] for row in read_records(path)}
        created = []
        for item in board:
            symbol = str(item.get("symbol") or "").strip().upper()
            source = latest.get(symbol)
            v2 = item.get("quality_dips_v2") or {}
            v3 = v2.get("quality_dips_v3") or {}
            if not source or not v3 or not _eligible_source(source, now):
                continue
            key = f"{now.date()}|{symbol}|{POLICY_VERSION}"
            oid = hashlib.sha256(key.encode()).hexdigest()
            if oid in existing:
                continue
            row = {
                "schema_version": 1,
                "observation_id": oid,
                "timestamp": now.isoformat(),
                "symbol": symbol,
                "price": source["price"],
                "source_timestamp": source["timestamp"],
                "source_snapshot": source,
                "strategy_version": "QUALITY_DIPS_V3",
                "policy_version": POLICY_VERSION,
                "execution_model_version": EXECUTION_VERSION,
                "policy_hash": hashlib.sha256(
                    json.dumps(v3.get("policy") or {}, sort_keys=True).encode()
                ).hexdigest(),
                "evidence_class": "FORWARD_COLLECTION",
                "classification": v3.get("patient_state"),
                "features": v2,
                "valuation": v2.get("normalization_value"),
                "prediction": v3,
                "confidence": v2.get("evidence_quality", "UNKNOWN"),
                "missing_data": v2.get("missing_v2_evidence", []),
                "future_outcome": "UNKNOWN",
                "execution": "MANUAL_ONLY",
                "live_capital_allowed": False,
                "automatic_real_money_execution": False,
            }
            append_record(path, row)
            existing.add(oid)
            created.append(row)
        return created
