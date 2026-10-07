from pathlib import Path

COMMAND=Path("frontend/src/app/page.tsx")
CRYPTO=Path("frontend/src/app/components/CryptoQualityDipsStatusPanel.tsx")
EVIDENCE=Path("frontend/src/app/research/page.tsx")
SURFACES=Path("frontend/src/app/research/surfaces/page.tsx")

def test_e114_command_center_system_health_group_is_named():
    text=COMMAND.read_text(encoding="utf-8")
    assert '<section aria-label="System health" className="flex flex-wrap gap-2">' in text
    assert '<Pill label="Scanner"' in text and '<Pill label="HL data"' in text

def test_e114_command_center_session_metric_group_is_named():
    text=COMMAND.read_text(encoding="utf-8")
    assert '<section aria-label="Session metrics" className="grid md:grid-cols-4 gap-3">' in text
    assert '<Stat label="Session open"' in text and '<Stat label="Session avg R"' in text

def test_e114_crypto_evidence_metric_group_is_named():
    text=CRYPTO.read_text(encoding="utf-8")
    assert 'role="group" aria-label="Evidence metrics"' in text
    assert '<Metric label="Observations"' in text and '<Metric label="Research gates"' in text

def test_e114_crypto_operational_context_group_is_named():
    text=CRYPTO.read_text(encoding="utf-8")
    assert 'role="group" aria-label="Operational context"' in text
    assert '<Context label="Operator status"' in text and '<Context label="Recovery"' in text

def test_e114_runtime_and_authority_contracts_preserved():
    command=COMMAND.read_text(encoding="utf-8")
    crypto=CRYPTO.read_text(encoding="utf-8")
    evidence=EVIDENCE.read_text(encoding="utf-8")
    surfaces=SURFACES.read_text(encoding="utf-8")
    assert "/api/live" in command and "}, 8000);" in command
    assert "REFRESH_MS=15000;" in crypto
    assert "/api/validation/challengers/research-evidence" in evidence and "setInterval(load,15000)" in evidence
    assert "Automatic real-money execution:" in evidence
    assert "Trading authority stays gated unless a separate validated roadmap execution explicitly unlocks it." in surfaces
