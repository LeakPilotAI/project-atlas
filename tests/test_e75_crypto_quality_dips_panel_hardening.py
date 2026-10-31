from pathlib import Path

PANEL = Path("frontend/src/app/components/CryptoQualityDipsStatusPanel.tsx")

def source():
    return PANEL.read_text(encoding="utf-8")

def test_e75_exposes_deterministic_refresh_freshness_without_actions():
    text = source()
    assert "REFRESH_MS=15000" in text
    assert "Last accepted response:" in text
    assert "Refresh cadence: 15s" in text
    assert "ageLabel(lastRefreshAt,now)" in text
    assert "setLastRefreshAt(Date.now())" in text
    assert "setInterval(()=>setNow(Date.now()),5000)" in text

def test_e75_distinguishes_transport_from_contract_rejection():
    text = source()
    assert '"TRANSPORT_ERROR"' in text
    assert "TRANSPORT FAILURE · API response unavailable" in text
    assert "CONTRACT REJECTED ·" in text
    assert 'transport==="CONNECTED"&&!result.ok' in text
    assert "consumeCryptoQualityDipsStatus(await response.json())" in text
    assert "fail closed" in text

def test_e75_accessibility_and_operator_boundary_remain_explicit():
    text = source()
    assert 'aria-labelledby="crypto-quality-dips-title"' in text
    assert 'id="crypto-quality-dips-title"' in text
    assert 'aria-live="polite"' in text
    assert 'role="status"' in text
    assert "Research only" in text
    assert "AUTHORITY LOCKED · READ ONLY" in text
    assert "Operator attention:" in text

def test_e75_remains_get_only_and_action_free():
    text = source()
    assert 'method:"GET"' in text
    for token in ('method:"POST"', 'method:"PUT"', 'method:"PATCH"', 'method:"DELETE"',
                  "Repair now", "Execute trade", "Place order", "Promote strategy",
                  "Enable live", "<button"):
        assert token not in text
