import json
from hashlib import sha256

import pytest

from app.backtest.manifest import (
    load_manifest,
    load_manifest_bytes,
)


def _manifest(dataset: bytes) -> bytes:
    payload = {
        "symbol": "BTC",
        "timeframe": "1h",
        "first_timestamp": "2026-01-01T00:00:00Z",
        "last_timestamp": "2026-01-01T01:00:00Z",
        "row_count": 2,
        "dataset_sha256": sha256(dataset).hexdigest(),
        "candles_source": "fixture",
        "funding_source": "fixture",
        "oi_source": "fixture",
        "rolling_volume_source": "fixture",
        "htf_context_source": "fixture",
        "pit_aligned": True,
        "current_state_backfill_used": False,
    }
    identity = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    payload["manifest_id"] = sha256(identity).hexdigest()[:20]
    return json.dumps(payload).encode()


def test_byte_and_path_validation_agree(tmp_path):
    dataset = b"fixture-dataset"
    manifest = _manifest(dataset)

    dataset_path = tmp_path / "dataset.csv"
    manifest_path = tmp_path / "manifest.json"

    dataset_path.write_bytes(dataset)
    manifest_path.write_bytes(manifest)

    assert load_manifest_bytes(manifest, dataset) == load_manifest(
        manifest_path, dataset_path
    )


def test_captured_dataset_mismatch_refused():
    manifest = _manifest(b"original")
    with pytest.raises(ValueError, match="dataset checksum"):
        load_manifest_bytes(manifest, b"replacement")


def test_captured_manifest_tampering_refused():
    dataset = b"fixture"
    payload = json.loads(_manifest(dataset))
    payload["symbol"] = "ETH"

    with pytest.raises(ValueError, match="manifest integrity"):
        load_manifest_bytes(json.dumps(payload).encode(), dataset)


def test_invalid_byte_inputs_refused():
    with pytest.raises(TypeError, match="manifest bytes"):
        load_manifest_bytes("not bytes")

    with pytest.raises(TypeError, match="dataset bytes"):
        load_manifest_bytes(_manifest(b"x"), "not bytes")
