from pathlib import Path
PANEL=Path("frontend/src/app/components/CryptoQualityDipsStatusPanel.tsx")
PAGE=Path("frontend/src/app/page.tsx")

def test_e74_panel_uses_only_public_get_and_e73_consumer():
    text=PANEL.read_text(encoding="utf-8")
    assert '"/api/investments/crypto-quality-dips/status"' in text
    assert 'method:"GET"' in text
    assert "consumeCryptoQualityDipsStatus(await response.json())" in text
    for token in ('method:"POST"','method:"PUT"','method:"PATCH"','method:"DELETE"'):
        assert token not in text

def test_e74_panel_is_visibly_research_only_and_authority_locked():
    text=PANEL.read_text(encoding="utf-8")
    assert "Crypto Quality Dips · Research only" in text
    assert "AUTHORITY LOCKED · READ ONLY" in text
    assert "No scoring, PAPER, execution, repair, or live-capital authority." in text
    for forbidden in ("Repair","Execute trade","Place order","Promote strategy","Enable live"):
        assert forbidden not in text

def test_e74_panel_fails_closed_for_transport_and_contract_failures():
    text=PANEL.read_text(encoding="utf-8")
    assert 'displayState:"UNAVAILABLE"' in text
    assert 'severity:"CRITICAL"' in text
    assert 'operatorAttentionRequired:true' in text
    assert 'gatesMet:false' in text
    assert '"NETWORK_OR_HTTP_ERROR"' in text
    assert "Status unavailable / fail closed" in text

def test_e74_command_center_mounts_crypto_panel():
    page=PAGE.read_text(encoding="utf-8")
    assert 'import CryptoQualityDipsStatusPanel from "@/app/components/CryptoQualityDipsStatusPanel"' in page
    assert "<CryptoQualityDipsStatusPanel />" in page
