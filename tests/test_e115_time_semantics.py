from pathlib import Path

COMMAND=Path("frontend/src/app/page.tsx")
CRYPTO=Path("frontend/src/app/components/CryptoQualityDipsStatusPanel.tsx")

def test_e115_relative_time_helper():
    text=COMMAND.read_text(encoding="utf-8")
    assert "function RelativeTime" in text
    assert "<time dateTime={parsed.toISOString()}>{ago(value)}</time>" in text

def test_e115_primary_ages_use_time_semantics():
    text=COMMAND.read_text(encoding="utf-8")
    assert "<RelativeTime value={live?.updated_at} />" in text
    assert "<RelativeTime value={h.last_cycle_at} />" in text
    assert "<RelativeTime value={live?.quality_dips?.last_scan_at} />" in text
    assert "<RelativeTime value={t.opened_at} />" in text

def test_e115_activity_ages_use_time_semantics():
    text=COMMAND.read_text(encoding="utf-8")
    for field in ("last_market_data","last_candles","last_evaluation","last_qualified","last_paper_open","last_discord_alert"):
        assert f"<RelativeTime value={{live?.activity?.{field}}} />" in text

def test_e115_crypto_response_time_semantics():
    text=CRYPTO.read_text(encoding="utf-8")
    assert "<time dateTime={new Date(lastRefreshAt).toISOString()}>{ageLabel(lastRefreshAt,now)}</time>" in text
    assert "Last accepted response:" in text and "Refresh cadence: 15s" in text

def test_e115_refresh_contracts_preserved():
    command=COMMAND.read_text(encoding="utf-8")
    crypto=CRYPTO.read_text(encoding="utf-8")
    assert "/api/live" in command and "}, 8000);" in command
    assert "REFRESH_MS=15000;" in crypto
