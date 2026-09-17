import json
from pathlib import Path

import pytest

from app.backtest.manifest import build_manifest,load_manifest,write_manifest


FIXTURE=Path("tests/fixtures/backtest_smoke.csv")


def test_manifest_records_dataset_identity_and_pit_provenance(tmp_path:Path):
    m=build_manifest(
        FIXTURE,
        candles_source="hyperliquid:candleSnapshot",
        funding_source="hyperliquid:fundingHistory",
        oi_source="historical-provider:oi",
        rolling_volume_source="historical-provider:rolling24h",
        htf_context_source="derived-from-prior-bars-only",
        pit_aligned=True,
    )
    assert m.symbol=="BTC";assert m.timeframe=="5m";assert m.row_count>0
    assert len(m.dataset_sha256)==64;assert m.current_state_backfill_used is False
    p=write_manifest(m,tmp_path/"manifest.json");payload=load_manifest(p,FIXTURE)
    assert payload["pit_aligned"] is True;assert payload["manifest_id"]


def test_manifest_rejects_missing_provenance_and_current_state_backfill():
    with pytest.raises(ValueError,match="missing provenance"):
        build_manifest(FIXTURE,candles_source="",funding_source="x",oi_source="x",rolling_volume_source="x",htf_context_source="x",pit_aligned=True)
    with pytest.raises(ValueError,match="current-state backfill"):
        build_manifest(FIXTURE,candles_source="x",funding_source="x",oi_source="x",rolling_volume_source="x",htf_context_source="x",pit_aligned=True,current_state_backfill_used=True)


def test_manifest_detects_dataset_tampering(tmp_path:Path):
    copy=tmp_path/"data.csv";copy.write_bytes(FIXTURE.read_bytes())
    m=build_manifest(copy,candles_source="x",funding_source="x",oi_source="x",rolling_volume_source="x",htf_context_source="x",pit_aligned=True)
    p=write_manifest(m,tmp_path/"manifest.json")
    copy.write_text(copy.read_text(encoding="utf-8")+"\n",encoding="utf-8")
    with pytest.raises(ValueError,match="checksum"):
        load_manifest(p,copy)


def test_manifest_load_rejects_incomplete_json(tmp_path:Path):
    p=tmp_path/"bad.json";p.write_text(json.dumps({"pit_aligned":True}),encoding="utf-8")
    with pytest.raises(ValueError,match="missing fields"):
        load_manifest(p,FIXTURE)
