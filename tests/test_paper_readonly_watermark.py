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


def test_watermarked_session_commits_each_tick_and_resumes(tmp_path, monkeypatch):
    from scripts.observation_runtime.paper_readonly_watermark import run_watermarked_readonly_paper_session
    from app.services import personal_paper_strategy_signal as signals
    path = tmp_path / "events.json"
    start = datetime(2026, 11, 7, tzinfo=UTC)
    advance_watermark(path, symbol="MSFT", provider_timestamp=start.isoformat())
    observed = []
    def fake_session(*, ticks, clock, previous_provider_timestamp, **dependencies):
        observed.append(previous_provider_timestamp)
        next_stamp = datetime.fromisoformat(previous_provider_timestamp) + timedelta(seconds=1)
        return {"last_provider_timestamp": next_stamp.isoformat(),
                "paper_fill_authorized": False, "live_order_authorized": False,
                "ticks": [{"timestamp": next_stamp.isoformat()}]}
    monkeypatch.setattr(signals, "run_bounded_readonly_paper_session", fake_session)
    args = dict(path=path, symbol="MSFT", enrolled=True, clock=lambda: start,
                provider=object())
    result = run_watermarked_readonly_paper_session(ticks=2, **args)
    assert result["completed"] == 2
    assert result["paper_fill_authorized"] is False
    assert read_watermark(path, symbol="MSFT") == (start + timedelta(seconds=2)).isoformat()
    run_watermarked_readonly_paper_session(ticks=1, **args)
    assert observed == [(start + timedelta(seconds=i)).isoformat() for i in range(3)]


def test_watermarked_session_requires_enrollment_and_prior_state(tmp_path, monkeypatch):
    from scripts.observation_runtime.paper_readonly_watermark import run_watermarked_readonly_paper_session
    from app.services import personal_paper_strategy_signal as signals
    path = tmp_path / "missing.json"
    args = dict(path=path, symbol="MSFT", ticks=1, clock=lambda: None,
                provider=object())
    with pytest.raises(ValueError, match="ENROLLMENT_REQUIRED"):
        run_watermarked_readonly_paper_session(enrolled=False, **args)
    with pytest.raises(ValueError, match="ENROLLED_STATE_MISSING"):
        run_watermarked_readonly_paper_session(enrolled=True, **args)
    start = datetime(2026, 11, 7, tzinfo=UTC)
    advance_watermark(path, symbol="MSFT", provider_timestamp=start.isoformat())
    def refused(**kwargs):
        raise ValueError("PROVIDER_DOWN")
    monkeypatch.setattr(signals, "run_bounded_readonly_paper_session", refused)
    with pytest.raises(ValueError, match="PROVIDER_DOWN"):
        run_watermarked_readonly_paper_session(enrolled=True, **args)
    assert read_watermark(path, symbol="MSFT") == start.isoformat()
