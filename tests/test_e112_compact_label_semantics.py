from pathlib import Path
COMMAND=Path("frontend/src/app/page.tsx")
BADGE=Path("frontend/src/app/components/SurfaceStatusBadge.tsx")
CRYPTO=Path("frontend/src/app/components/CryptoQualityDipsStatusPanel.tsx")
EVIDENCE=Path("frontend/src/app/research/page.tsx")
SURFACES=Path("frontend/src/app/research/surfaces/page.tsx")

def test_e112_api_status_expansion():
    text=COMMAND.read_text(encoding="utf-8")
    assert 'Application programming interface down' in text
    assert 'Application programming interface connected' in text
    assert '"API down"' in text and '"API connected"' in text

def test_e112_api_alert_expansion():
    text=COMMAND.read_text(encoding="utf-8")
    assert 'aria-label="Application programming interface error"' in text
    assert 'API not reachable on port 8000' in text

def test_e112_badges_pair_label_and_meaning():
    text=BADGE.read_text(encoding="utf-8")
    for status in ("ACTIVE_EVIDENCE","RESEARCH_ONLY","OPERATIONAL_VIEW","GATED"):
        assert status in text
    assert "{definition.label}" in text
    assert "{definition.meaning}" in text

def test_e112_visible_compact_copy_preserved():
    text=COMMAND.read_text(encoding="utf-8")
    assert '<Pill label="Paper"' in text
    assert '<Pill label="HL data"' in text

def test_e112_runtime_contracts_preserved():
    command=COMMAND.read_text(encoding="utf-8")
    crypto=CRYPTO.read_text(encoding="utf-8")
    evidence=EVIDENCE.read_text(encoding="utf-8")
    surfaces=SURFACES.read_text(encoding="utf-8")
    assert "/api/live" in command and "}, 8000);" in command
    assert 'REFRESH_MS=15000;' in crypto
    assert "/api/validation/challengers/research-evidence" in evidence
    assert "setInterval(load,15000)" in evidence
    assert "Automatic real-money execution:" in evidence
    assert "Trading authority stays gated unless a separate validated roadmap execution explicitly unlocks it." in surfaces
