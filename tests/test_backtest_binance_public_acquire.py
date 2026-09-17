from pathlib import Path

from app.backtest.binance_public_acquire import _months, plan


def test_months_are_deterministic_half_open():
    assert _months("2024-07-01T00:00:00Z", "2025-01-01T00:00:00Z") == [
        "2024-07", "2024-08", "2024-09", "2024-10", "2024-11", "2024-12"
    ]


def test_2024_h2_plan_is_free_no_aws_and_has_36_objects(tmp_path: Path):
    payload = plan(
        start_utc="2024-07-01T00:00:00Z",
        end_utc="2025-01-01T00:00:00Z",
        raw_root=tmp_path,
    )
    assert len(payload["objects"]) == 36  # 3 symbols x 2 intervals x 6 months
    assert payload["authentication_required"] is False
    assert payload["paid_service_required"] is False
    assert payload["aws_required"] is False
    assert payload["candles_only"] is True
    assert payload["pit_oi_context_complete"] is False
    assert payload["live_capital_allowed"] is False
    assert payload["automatic_real_money_execution"] is False
    assert payload["current_state_backfill_allowed"] is False


def test_plan_uses_usdm_futures_public_paths_and_checksums(tmp_path: Path):
    payload = plan(
        start_utc="2024-07-01T00:00:00Z",
        end_utc="2024-08-01T00:00:00Z",
        raw_root=tmp_path,
        symbols=("BTC",),
        intervals=("5m",),
    )
    obj = payload["objects"][0]
    assert obj["provider_symbol"] == "BTCUSDT"
    assert obj["url"].endswith("/data/futures/um/monthly/klines/BTCUSDT/5m/BTCUSDT-5m-2024-07.zip")
    assert obj["checksum_url"] == obj["url"] + ".CHECKSUM"
    assert obj["local_zip"].endswith("BTCUSDT\\5m\\BTCUSDT-5m-2024-07.zip") or obj["local_zip"].endswith("BTCUSDT/5m/BTCUSDT-5m-2024-07.zip")


def test_plan_rejects_non_representative_symbol(tmp_path: Path):
    try:
        plan(start_utc="2024-07-01T00:00:00Z", end_utc="2024-08-01T00:00:00Z", raw_root=tmp_path, symbols=("DOGE",))
    except ValueError as exc:
        assert "unsupported representative symbols" in str(exc)
    else:
        raise AssertionError("expected fail-closed symbol validation")


def test_plan_rejects_unapproved_interval(tmp_path: Path):
    try:
        plan(start_utc="2024-07-01T00:00:00Z", end_utc="2024-08-01T00:00:00Z", raw_root=tmp_path, intervals=("1m",))
    except ValueError as exc:
        assert "unsupported intervals" in str(exc)
    else:
        raise AssertionError("expected fail-closed interval validation")
