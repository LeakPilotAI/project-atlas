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


def test_watermark_writer_refuses_second_owner(tmp_path):
    from scripts.observation_runtime.paper_readonly_watermark import readonly_watermark_writer
    path = tmp_path / "owned.json"
    with readonly_watermark_writer(path):
        with pytest.raises(ValueError, match="WRITER_ALREADY_OWNED"):
            with readonly_watermark_writer(path):
                pass
    with readonly_watermark_writer(path):
        pass
    assert (tmp_path / "owned.json.writer.lock").is_file()


def test_watermarked_session_releases_writer_after_provider_failure(tmp_path, monkeypatch):
    from scripts.observation_runtime.paper_readonly_watermark import (
        run_watermarked_readonly_paper_session, readonly_watermark_writer)
    from app.services import personal_paper_strategy_signal as signals
    path = tmp_path / "recovery.json"
    stamp = datetime(2026, 11, 7, tzinfo=UTC)
    advance_watermark(path, symbol="MSFT", provider_timestamp=stamp.isoformat())
    def failed(**kwargs):
        raise ValueError("PROVIDER_LOST")
    monkeypatch.setattr(signals, "run_bounded_readonly_paper_session", failed)
    with pytest.raises(ValueError, match="PROVIDER_LOST"):
        run_watermarked_readonly_paper_session(
            path=path, symbol="MSFT", enrolled=True, ticks=1, clock=lambda: stamp)
    with readonly_watermark_writer(path):
        assert read_watermark(path, symbol="MSFT") == stamp.isoformat()


def test_dangling_watermark_symlink_cannot_be_treated_as_fresh_state(tmp_path):
    from scripts.observation_runtime.paper_readonly_watermark import readonly_watermark_writer
    link = tmp_path / "watermark.json"
    try:
        link.symlink_to(tmp_path / "nonexistent.json")
    except (OSError, NotImplementedError):
        pytest.skip("Windows symlink creation requires permission")
    with pytest.raises(ValueError, match="STORAGE_REFUSED"):
        read_watermark(link, symbol="MSFT")
    with pytest.raises(ValueError, match="STORAGE_REFUSED"):
        advance_watermark(link, symbol="MSFT", provider_timestamp="2026-11-07T00:00:00+00:00")
    with pytest.raises(ValueError, match="LOCK_PARENT_INVALID"):
        with readonly_watermark_writer(link):
            pass


def test_writer_lock_path_symlink_is_refused(tmp_path):
    from scripts.observation_runtime.paper_readonly_watermark import readonly_watermark_writer
    path = tmp_path / "watermark.json"
    link = tmp_path / "watermark.json.writer.lock"
    try:
        link.symlink_to(tmp_path / "not-there")
    except (OSError, NotImplementedError):
        pytest.skip("Windows symlink creation requires permission")
    with pytest.raises(ValueError, match="LOCK_PATH_REFUSED"):
        with readonly_watermark_writer(path):
            pass


def test_interrupted_pending_write_fails_closed_without_overwriting(tmp_path):
    path = tmp_path / "events.json"
    initial = datetime(2026, 11, 7, tzinfo=UTC)
    advance_watermark(path, symbol="MSFT", provider_timestamp=initial.isoformat())
    pending = tmp_path / "events.json.pending"
    pending.write_text("interrupted-newer-event", encoding="utf-8")
    original = path.read_bytes()
    with pytest.raises(ValueError, match="INTERRUPTED_WRITE"):
        advance_watermark(path, symbol="MSFT",
                          provider_timestamp=(initial + timedelta(seconds=1)).isoformat())
    assert path.read_bytes() == original
    assert pending.read_text(encoding="utf-8") == "interrupted-newer-event"


def test_iex_callback_consumer_persists_events_and_refuses_replay(tmp_path):
    from scripts.observation_runtime.paper_readonly_watermark import ReadonlyIEXEventConsumer
    path = tmp_path / "iex.json"
    stamp = datetime(2026, 11, 7, tzinfo=UTC)
    advance_watermark(path, symbol="MSFT", provider_timestamp=stamp.isoformat())
    event = {"symbol": "MSFT", "provider": "ALPACA_IEX",
             "timestamp": (stamp + timedelta(seconds=1)).isoformat(),
             "paper_fill_authorized": False, "live_order_authorized": False}
    with ReadonlyIEXEventConsumer(path=path, symbol="MSFT") as consumer:
        consumer.on_fresh_quote(event)
        assert consumer.accepted == 1
        with pytest.raises(ValueError, match="REPLAY_REFUSED"):
            consumer.on_fresh_quote(event)
    assert read_watermark(path, symbol="MSFT") == event["timestamp"]
    with ReadonlyIEXEventConsumer(path=path, symbol="MSFT") as consumer:
        with pytest.raises(ValueError, match="REPLAY_REFUSED"):
            consumer.on_fresh_quote(event)
    with pytest.raises(ValueError, match="NOT_STARTED"):
        consumer.on_fresh_quote(event)


def test_iex_callback_consumer_refuses_uninitialized_and_wrong_authority(tmp_path):
    from scripts.observation_runtime.paper_readonly_watermark import ReadonlyIEXEventConsumer
    path = tmp_path / "iex.json"
    with pytest.raises(ValueError, match="PRIOR_STATE_REQUIRED"):
        with ReadonlyIEXEventConsumer(path=path, symbol="MSFT"):
            pass
    stamp = datetime(2026, 11, 7, tzinfo=UTC)
    advance_watermark(path, symbol="MSFT", provider_timestamp=stamp.isoformat())
    with ReadonlyIEXEventConsumer(path=path, symbol="MSFT") as consumer:
        with pytest.raises(ValueError, match="EVENT_REFUSED"):
            consumer.on_fresh_quote({"symbol": "MSFT", "provider": "ALPACA_IEX",
                                     "timestamp": (stamp + timedelta(seconds=1)).isoformat(),
                                     "paper_fill_authorized": True, "live_order_authorized": False})
        assert consumer.accepted == 0


def test_iex_callback_recomputes_v3_before_committing_watermark(tmp_path):
    from scripts.observation_runtime.paper_readonly_watermark import ReadonlyIEXEventConsumer
    path = tmp_path / "iex-v3.json"
    now = datetime(2026, 11, 7, tzinfo=UTC)
    advance_watermark(path, symbol="MSFT", provider_timestamp=(now - timedelta(seconds=2)).isoformat())
    research = {"symbol": "MSFT", "source_verified": True, "timestamp": now.isoformat(),
                "normalization_value": {"conservative": 95, "base": 100, "optimistic": 105},
                "quality_score": 80, "fundamentals_score": 80,
                "valuation_score": 70, "drawdown_percentile": 80,
                "evidence_quality": "HIGH", "thesis": "INTACT", "value_trap": False}
    event = {"symbol": "MSFT", "provider": "ALPACA_IEX",
             "timestamp": (now - timedelta(seconds=1)).isoformat(),
             "bid": "80", "ask": "80", "bid_lots": 2, "ask_lots": 2,
             "paper_fill_authorized": False, "live_order_authorized": False}
    with ReadonlyIEXEventConsumer(path=path, symbol="MSFT",
                                  research=research, clock=lambda: now) as consumer:
        consumer.on_fresh_quote(event)
        assert consumer.last_strategy["candidate"] is True
        assert consumer.last_strategy["paper_fill_authorized"] is False
        assert consumer.last_strategy["research_provenance_attested"] is False
        prior = consumer.last_event
        with pytest.raises(ValueError, match="BID_ASK_INVALID"):
            consumer.on_fresh_quote({**event, "timestamp": now.isoformat(), "bid": "90", "ask": "80"})
        assert consumer.last_event == prior
        assert consumer.accepted == 1
    assert read_watermark(path, symbol="MSFT") == prior
