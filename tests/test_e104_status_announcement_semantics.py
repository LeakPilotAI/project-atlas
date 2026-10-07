from pathlib import Path

COMMAND=Path("frontend/src/app/page.tsx")
CRYPTO=Path("frontend/src/app/components/CryptoQualityDipsStatusPanel.tsx")
EVIDENCE=Path("frontend/src/app/research/page.tsx")
SURFACES=Path("frontend/src/app/research/surfaces/page.tsx")

def test_e104_command_center_connecting_state_is_polite_atomic_status():
    text=COMMAND.read_text(encoding="utf-8")
    assert '<p role="status" aria-live="polite" aria-atomic="true" className="text-sm tracking-wide text-zinc-500">Connecting to Atlas…</p>' in text

def test_e104_command_center_connection_state_remains_polite_atomic_and_errors_alert():
    text=COMMAND.read_text(encoding="utf-8")
    assert '<div role="status" aria-live="polite" aria-atomic="true" className={error ? "text-rose-400" : "text-emerald-400"}>' in text
    assert '<div role="alert" className="rounded-xl border border-rose-500/30' in text

def test_e104_crypto_transport_is_polite_atomic_status_and_failure_is_alert():
    text=CRYPTO.read_text(encoding="utf-8")
    assert '<div role="status" aria-live="polite" aria-atomic="true" className="mt-3 flex flex-wrap' in text
    assert 'role="alert">Status unavailable / fail closed · {failureLabel}</div>' in text

def test_e104_research_fetch_failure_remains_alert_without_copy_change():
    text=EVIDENCE.read_text(encoding="utf-8")
    assert 'setError("Research evidence status unavailable. Atlas remains NOT READY by default.")' in text
    assert '{error&&<div role="alert"' in text

def test_e104_semantic_hardening_preserves_refresh_and_boundary_contracts():
    command=COMMAND.read_text(encoding="utf-8"); crypto=CRYPTO.read_text(encoding="utf-8"); evidence=EVIDENCE.read_text(encoding="utf-8"); surfaces=SURFACES.read_text(encoding="utf-8")
    assert "/api/live" in command and "}, 8000);" in command
    assert 'REFRESH_MS=15000;' in crypto
    assert "/api/validation/challengers/research-evidence" in evidence and "setInterval(load,15000)" in evidence
    assert "Trading authority stays gated unless a separate validated roadmap execution explicitly unlocks it." in surfaces
