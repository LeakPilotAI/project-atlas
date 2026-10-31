"""Deterministic provenance manifests for Atlas historical datasets."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path

from app.backtest.io import load_historical_contexts


@dataclass(frozen=True)
class HistoricalDatasetManifest:
    symbol: str
    timeframe: str
    first_timestamp: str
    last_timestamp: str
    row_count: int
    dataset_sha256: str
    candles_source: str
    funding_source: str
    oi_source: str
    rolling_volume_source: str
    htf_context_source: str
    pit_aligned: bool
    current_state_backfill_used: bool = False
    notes: str = ""

    def validate(self) -> None:
        required={
            "candles_source":self.candles_source,
            "funding_source":self.funding_source,
            "oi_source":self.oi_source,
            "rolling_volume_source":self.rolling_volume_source,
            "htf_context_source":self.htf_context_source,
        }
        missing=[name for name,value in required.items() if not str(value).strip()]
        if missing:
            raise ValueError(f"manifest missing provenance fields: {', '.join(missing)}")
        if not self.pit_aligned:
            raise ValueError("historical dataset provenance must be point-in-time aligned")
        if self.current_state_backfill_used:
            raise ValueError("current-state backfill is forbidden for historical backtests")


def _sha256_file(path:Path)->str:
    h=sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda:fh.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(
    dataset_path:Path,
    *,
    candles_source:str,
    funding_source:str,
    oi_source:str,
    rolling_volume_source:str,
    htf_context_source:str,
    pit_aligned:bool,
    current_state_backfill_used:bool=False,
    notes:str="",
)->HistoricalDatasetManifest:
    dataset_path=Path(dataset_path)
    contexts=load_historical_contexts(dataset_path)
    bars=[row.bar for row in contexts]
    manifest=HistoricalDatasetManifest(
        symbol=bars[0].symbol,
        timeframe=bars[0].timeframe,
        first_timestamp=bars[0].timestamp,
        last_timestamp=bars[-1].timestamp,
        row_count=len(bars),
        dataset_sha256=_sha256_file(dataset_path),
        candles_source=candles_source,
        funding_source=funding_source,
        oi_source=oi_source,
        rolling_volume_source=rolling_volume_source,
        htf_context_source=htf_context_source,
        pit_aligned=bool(pit_aligned),
        current_state_backfill_used=bool(current_state_backfill_used),
        notes=notes,
    )
    manifest.validate()
    return manifest


def write_manifest(manifest:HistoricalDatasetManifest,path:Path)->Path:
    manifest.validate();path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    payload=asdict(manifest)
    payload["manifest_id"]=sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()[:20]
    path.write_text(json.dumps(payload,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    return path


def load_manifest_bytes(
    manifest_bytes: bytes,
    dataset_bytes: bytes | None = None,
) -> dict:
    """Validate a captured manifest against optional captured dataset bytes."""
    if not isinstance(manifest_bytes, bytes):
        raise TypeError("manifest bytes required")
    if dataset_bytes is not None and not isinstance(dataset_bytes, bytes):
        raise TypeError("dataset bytes required")
    payload = json.loads(manifest_bytes.decode("utf-8"))
    if not isinstance(payload,dict):raise ValueError("manifest must be a JSON object")
    required={"symbol","timeframe","first_timestamp","last_timestamp","row_count","dataset_sha256","candles_source","funding_source","oi_source","rolling_volume_source","htf_context_source","pit_aligned","current_state_backfill_used","manifest_id"}
    missing=sorted(required-set(payload))
    if missing:raise ValueError(f"manifest missing fields: {', '.join(missing)}")
    if type(payload["pit_aligned"]) is not bool:
        raise ValueError("manifest PIT alignment must be boolean")
    if type(payload["current_state_backfill_used"]) is not bool:
        raise ValueError("manifest backfill status must be boolean")
    if not isinstance(payload["dataset_sha256"], str) or len(payload["dataset_sha256"]) != 64 or any(c not in "0123456789abcdef" for c in payload["dataset_sha256"]):
        raise ValueError("manifest dataset checksum is invalid")
    for field in ("candles_source", "funding_source", "oi_source", "rolling_volume_source", "htf_context_source"):
        if not isinstance(payload[field], str) or not payload[field].strip():
            raise ValueError(f"manifest source identity invalid: {field}")
    identity = {k: v for k, v in payload.items() if k != "manifest_id"}
    expected_id = sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:20]
    if not isinstance(payload["manifest_id"], str) or payload["manifest_id"] != expected_id:
        raise ValueError("manifest integrity verification failed")
    if payload["pit_aligned"] is not True:raise ValueError("manifest is not PIT aligned")
    if payload["current_state_backfill_used"] is True:raise ValueError("manifest used forbidden current-state backfill")
    if dataset_bytes is not None and sha256(dataset_bytes).hexdigest() != payload["dataset_sha256"]:
        raise ValueError("dataset checksum does not match manifest")
    return payload


def load_manifest(path: Path, dataset_path: Path | None = None) -> dict:
    """Existing path-based manifest validation interface."""
    manifest_bytes = Path(path).read_bytes()
    dataset_bytes = (
        Path(dataset_path).read_bytes()
        if dataset_path is not None
        else None
    )
    return load_manifest_bytes(manifest_bytes, dataset_bytes)
