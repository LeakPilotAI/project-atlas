from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.services.runtime_hardening import harden_adapter, harden_manual_service, safe_iter_jsonl


def test_safe_iter_jsonl_quarantines_bad_bytes_and_bad_json(tmp_path: Path):
    path = tmp_path / "journal.jsonl"
    with path.open("wb") as handle:
        handle.write(json.dumps({"event": "open", "trade_id": "ok"}).encode("utf-8") + b"\n")
        handle.write(b"\xff\xfebad-json\n")
        handle.write(b'{"event":"close","trade_id":"ok"}\n')

    rows = safe_iter_jsonl(path)

    assert rows[0]["trade_id"] == "ok"
    assert rows[1]["event"] == "_malformed"
    assert rows[2]["event"] == "close"


class FlakyAdapter:
    def __init__(self):
        self.calls = 0

    async def _post(self, body):
        self.calls += 1
        if self.calls < 3:
            raise httpx.ConnectTimeout("temporary")
        return {"ok": True, "body": body}


@pytest.mark.asyncio
async def test_adapter_retries_transient_timeout_then_recovers():
    adapter = harden_adapter(FlakyAdapter())
    result = await adapter._post({"type": "meta"})

    assert result["ok"] is True
    assert adapter.calls == 3
    assert adapter._atlas_consecutive_rest_failures == 0
    assert adapter._atlas_last_rest_success is not None


class FakeManualService:
    def __init__(self):
        self.last_snapshot = {
            "setups": [{
                "symbol": "BTC",
                "state": "L1_ACTIVE",
                "alert_eligible": True,
                "discovery_stale": False,
            }],
            "alert_candidates": [{"symbol": "BTC"}],
        }
        self.persisted = 0

    async def refresh(self):
        raise httpx.ConnectTimeout("market data unavailable")

    def _persist_state(self):
        self.persisted += 1


@pytest.mark.asyncio
async def test_manual_service_fails_closed_when_market_refresh_fails():
    service = harden_manual_service(FakeManualService())

    with pytest.raises(httpx.ConnectTimeout):
        await service.refresh()

    setup = service.last_snapshot["setups"][0]
    assert setup["state"] == "WAIT"
    assert setup["discovery_stale"] is True
    assert setup["alert_eligible"] is False
    assert service.last_snapshot["alert_candidates"] == []
    assert service.last_snapshot["data_status"] == "STALE"
    assert "ConnectTimeout" in service.last_snapshot["data_error"]
    assert service.persisted == 1
