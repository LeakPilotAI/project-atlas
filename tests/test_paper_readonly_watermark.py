from datetime import UTC, datetime, timedelta
import pytest

from scripts.observation_runtime.paper_readonly_watermark import (
    read_watermark, advance_watermark)


def test_readonly_watermark_persists_and_rejects_replay(tmp_path):
    path = tmp_path / "iex-watermark.json"
    stamp = datetime(2026, 11, 7, tzinfo=UTC)
    assert read_watermark(path, symbol="MSFT") is None
    result = advance_watermark(path, symbol="MSFT", provider_timestamp=stamp.isoformat())
    assert result["paper_fill_authorized"] is False
    assert result["live_order_authorized"] is False
    assert read_watermark(path, symbol="MSFT") == stamp.isoformat()
    original = path.read_bytes()
    for value in (stamp, stamp - timedelta(seconds=1)):
        with pytest.raises(ValueError, match="REPLAY_REFUSED"):
            advance_watermark(path, symbol="MSFT", provider_timestamp=value.isoformat())
    assert path.read_bytes() == original
    later = stamp + timedelta(seconds=1)
    advance_watermark(path, symbol="MSFT", provider_timestamp=later.isoformat())
    assert read_watermark(path, symbol="MSFT") == later.isoformat()


def test_readonly_watermark_refuses_corruption_and_identity_mismatch(tmp_path):
    path = tmp_path / "watermark.json"
    path.write_text("not-json", encoding="utf-8")
    with pytest.raises(ValueError):
        read_watermark(path, symbol="MSFT")
    with pytest.raises(ValueError):
        advance_watermark(path, symbol="MSFT", provider_timestamp="2026-11-07T00:00:00+00:00")
    path.unlink()
    advance_watermark(path, symbol="MSFT", provider_timestamp="2026-11-07T00:00:00+00:00")
    with pytest.raises(ValueError, match="CONTENT_REFUSED"):
        read_watermark(path, symbol="AVGO")
