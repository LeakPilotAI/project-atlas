from datetime import datetime, timezone

import pytest

from scripts.observation_runtime.r7e47cp_market_signals import analyze_market
from scripts.observation_runtime.r7e47de_research_bridge import bridge_research

NOW = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)


def rows(now=NOW):
    return [{"timestamp": now, "Close": 102., "Volume": 100}]


def quote(**changes):
    return {"symbol": "AAPL", "price": 102., "source": "FIXTURE",
            "session": "PRE_MARKET", "timestamp": NOW, **changes}


def test_research_only_cannot_be_disabled_by_input():
    with pytest.raises(ValueError):
        bridge_research(quote(research_only=False), rows(), 100., now=NOW)


def test_missing_source_is_not_invented():
    q = quote()
    del q["source"]
    with pytest.raises(ValueError):
        bridge_research(q, rows(), 100., now=NOW)


def test_declared_session_must_match_timestamp():
    with pytest.raises(ValueError):
        bridge_research(quote(session="REGULAR"), rows(), 100., now=NOW)


def test_holiday_is_not_a_trading_session():
    now = datetime(2026, 11, 26, 15, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        analyze_market("AAPL", rows(now), 100., now=now)


def test_duplicate_minutes_cannot_double_count_volume():
    r = rows()
    with pytest.raises(ValueError):
        analyze_market("AAPL", r+r, 100., now=NOW)


def test_future_row_cannot_be_silently_dropped():
    r = rows()+rows(datetime(2026, 10, 19, 12, 1, tzinfo=timezone.utc))
    with pytest.raises(ValueError):
        analyze_market("AAPL", r, 100., now=NOW)


def test_invalid_argument_count_refused():
    with pytest.raises((TypeError, ValueError)):
        bridge_research(quote(), rows(), 100., None, None, observation=quote(), candles=rows(), previous_close=100., now=NOW)


@pytest.mark.parametrize("value", [True, None, -1, float("nan"), float("inf")])
def test_invalid_reference_never_becomes_gap(value):
    with pytest.raises(ValueError):
        analyze_market("AAPL", rows(), value, now=NOW)


@pytest.mark.parametrize("field,value", [("Volume", True), ("Volume", 1.5), ("Volume", -1), ("Close", True), ("Close", float("inf")), ("High", 100)])
def test_invalid_candle_fields_refused(field, value):
    with pytest.raises(ValueError):
        analyze_market("AAPL", [{**rows()[0], field: value}], 100., now=NOW)


def test_dated_close_requires_immediately_preceding_session():
    ref = {"previous_close": 100., "previous_session_date": "2026-10-15", "source": "FIXTURE"}
    with pytest.raises(ValueError):
        analyze_market("AAPL", rows(), ref, now=NOW)
    ref["previous_session_date"] = "2026-10-16"
    signal = analyze_market("AAPL", rows(), ref, now=NOW)
    assert signal["previous_close_status"] == "DATED_CALLER_REFERENCE"
    assert signal["previous_session_date"] == "2026-10-16"
    assert analyze_market("AAPL", rows(), 100., now=NOW)["previous_close_status"] == "UNDATED_CALLER_REFERENCE"


def test_momentum_does_not_mix_premarket_and_regular():
    now = datetime.fromisoformat("2026-10-19T09:32:00-04:00")
    candles = [{"timestamp": datetime.fromisoformat(ts), "Close": p, "Volume": 10} for ts, p in [
        ("2026-10-19T08:00:00-04:00", 90), ("2026-10-19T09:30:00-04:00", 100), ("2026-10-19T09:32:00-04:00", 102)]]
    signal = analyze_market("AAPL", candles, 100., now=now)
    assert signal["session_momentum_percent"] == 2.
    assert signal["premarket_volume"] == 10
    assert signal["regular_volume"] == 20


@pytest.mark.parametrize("stamp,session", [
    ("2026-11-27T12:59:00-05:00", "REGULAR"),
    ("2026-11-27T13:00:00-05:00", "AFTER_HOURS"),
    ("2026-11-02T04:00:00-05:00", "PRE_MARKET"),
    ("2026-03-09T04:00:00-04:00", "PRE_MARKET"),
])
def test_calendar_early_close_and_dst(stamp, session):
    now = datetime.fromisoformat(stamp)
    assert analyze_market("AAPL", rows(now), 100., now=now)["session"] == session


@pytest.mark.parametrize("stamp", ["2026-10-18T08:00:00-04:00", "2026-12-25T10:00:00-05:00", "2029-10-19T08:00:00-04:00"])
def test_closed_or_unsupported_calendar_refused(stamp):
    now = datetime.fromisoformat(stamp)
    with pytest.raises(ValueError):
        analyze_market("AAPL", rows(now), 100., now=now)


def test_same_timestamp_conflicting_rows_refused():
    with pytest.raises(ValueError):
        analyze_market("AAPL", rows()+[{**rows()[0], "Close": 500}], 100., now=NOW)


def test_rvol_uses_complete_same_session_windows_only():
    from datetime import timedelta

    from app.investment.offline_research import rank_research
    now = datetime.fromisoformat("2026-10-19T04:02:00-04:00")
    current = [{"timestamp": now-timedelta(minutes=i), "Close": 102., "Volume": 20} for i in (2,1,0)]
    history = [{"timestamp": datetime.fromisoformat(f"2026-10-{day:02d}T04:{minute:02d}:00-04:00"), "Close": 100., "Volume": 10}
               for day in (12,13,14,15,16) for minute in (0,1)]
    signal = analyze_market("AAPL", current, 100., now=now, historical_candles=history)
    assert signal["relative_volume"] == 2.
    assert signal["baseline_sessions"] == 5
    assert signal["baseline_mean_volume"] == 20
    assert signal["volume_window_completed_minutes"] == 2
    insufficient = analyze_market("AAPL", current, 100., now=now, historical_candles=history[:-1])
    assert insufficient["relative_volume"] is None
    assert insufficient["baseline_sessions"] == 4
    assert insufficient["relative_volume_status"] == "BASELINE_INSUFFICIENT"
    incomplete = analyze_market("AAPL", current[:1]+current[2:], 100., now=now, historical_candles=history)
    assert incomplete["relative_volume_status"] == "CURRENT_WINDOW_INCOMPLETE"
    other = {**signal, "symbol": "MSFT"}
    assert [s["symbol"] for s in rank_research([other, signal])] == ["AAPL", "MSFT"]
    with pytest.raises(ValueError):
        rank_research([signal, signal])


def test_baseline_cannot_include_today_or_future():
    with pytest.raises(ValueError):
        analyze_market("AAPL", rows(), 100., now=NOW, historical_candles=rows())


def test_zero_volume_baseline_is_not_infinite_rvol():
    from datetime import timedelta
    now = datetime.fromisoformat("2026-10-19T04:01:00-04:00")
    current = rows(now)+rows(now-timedelta(minutes=1))
    hist = [{"timestamp": datetime.fromisoformat(f"2026-10-{day}T04:00:00-04:00"), "Close": 100, "Volume": 0} for day in (12,13,14,15,16)]
    result = analyze_market("AAPL", current, 100., now=now, historical_candles=hist)
    assert result["relative_volume"] is None
    assert result["relative_volume_status"] == "ZERO_BASELINE"


@pytest.mark.parametrize("changes", [{"trading_enabled": True}, {"research_only": "true"}, {"execution_authority": "false"}, {"source": 123}, {"symbol": "../data"}])
def test_research_metadata_not_authority(changes):
    with pytest.raises(ValueError):
        bridge_research(quote(**changes), rows(), 100., now=NOW)


def test_after_hours_alias_and_boolean_field():
    now = datetime.fromisoformat("2026-10-19T16:01:00-04:00")
    from scripts.observation_runtime.r7e47cq_signal_pipeline import (
        observe_equity_research,
    )
    result = observe_equity_research(quote_observation=quote(timestamp=now, session="POST_MARKET"), candle_data=rows(now), previous_close=100., now=now)
    assert result["session"] == result["quote_session"] == "AFTER_HOURS"



def test_after_hours_crossing_utc_midnight_stays_same_et_session():
    now = datetime.fromisoformat("2026-11-02T19:00:00-05:00")
    then = datetime.fromisoformat("2026-11-02T18:59:00-05:00")
    result = analyze_market("AAPL", rows(then),100.,now=now)
    assert result["session"] == "AFTER_HOURS"


@pytest.mark.parametrize("kwargs", [{"max_quote_age_seconds": True}, {"max_candle_age_seconds": True}, {"now": None, "current_time": None}, {"unknown_threshold": 1}])
def test_invalid_thresholds_or_aliases_refused(kwargs):
    with pytest.raises((TypeError, ValueError)):
        bridge_research(quote(),rows(),100.,**({"now": NOW}|kwargs))


def test_scalar_symbol_hint_cannot_override_identity():
    with pytest.raises(ValueError):
        bridge_research("MSFT",quote(),rows(),100.,now=NOW)


def test_strict_dataframe_conversion_preserves_original_filtering_api():
    import pandas as pd

    from scripts.observation_runtime.r7e47cn_yahoo_candles import dataframe_to_candles
    frame=pd.DataFrame({"Close":[102.,-1.],"Volume":[10,20]},index=pd.DatetimeIndex(["2026-10-19T07:59:00-04:00","2026-10-19T08:00:00-04:00"]))
    assert len(dataframe_to_candles(frame)) == 1
    with pytest.raises(ValueError): dataframe_to_candles(frame,strict=True)


def test_prior_daily_close_cannot_skip_last_session():
    import pandas as pd

    from scripts.observation_runtime.r7e47ct_previous_close import (
        extract_previous_close,
    )
    frame=pd.DataFrame({"Close":[100.]},index=pd.DatetimeIndex(["2026-10-15T00:00:00-04:00"]))
    with pytest.raises(ValueError): extract_previous_close(frame,observation_time=NOW)


def test_holiday_previous_close_and_duplicate_daily_refused():
    import pandas as pd

    from scripts.observation_runtime.r7e47ct_previous_close import (
        extract_previous_close,
    )
    now=datetime.fromisoformat("2026-11-27T08:00:00-05:00")
    frame=pd.DataFrame({"Close":[100.,999.]},index=pd.DatetimeIndex(["2026-11-25T00:00:00-05:00","2026-11-26T00:00:00-05:00"]))
    assert extract_previous_close(frame,observation_time=now)["previous_close"] == 100.
    frame=pd.concat([frame.iloc[:1],frame.iloc[:1]])
    with pytest.raises(ValueError): extract_previous_close(frame,observation_time=now)
