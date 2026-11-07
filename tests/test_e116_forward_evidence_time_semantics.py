from pathlib import Path

EVIDENCE=Path("frontend/src/app/research/page.tsx")
COMMAND=Path("frontend/src/app/page.tsx")
CRYPTO=Path("frontend/src/app/components/CryptoQualityDipsStatusPanel.tsx")
SURFACES=Path("frontend/src/app/research/surfaces/page.tsx")

def test_e116_forward_evidence_valid_timestamps_are_machine_readable():
    text=EVIDENCE.read_text(encoding="utf-8")
    assert 'function when(v?:string){if(!v)return "unknown time";const d=new Date(v);return Number.isNaN(d.getTime())?v:<time dateTime={d.toISOString()}>{d.toLocaleString()}</time>}' in text

def test_e116_forward_evidence_timestamp_fallbacks_are_preserved():
    text=EVIDENCE.read_text(encoding="utf-8")
    assert 'if(!v)return "unknown time"' in text
    assert 'Number.isNaN(d.getTime())?v:' in text

def test_e116_existing_timestamp_consumers_remain_intact():
    text=EVIDENCE.read_text(encoding="utf-8")
    assert "{when(point.timestamp)}" in text
    assert "{when(point.from_timestamp)} → {when(point.to_timestamp)}" in text
    assert "transition {when(check.transition_timestamp)} → confirm {when(check.confirmation_timestamp)}" in text

def test_e116_prior_machine_readable_time_contracts_remain_intact():
    command=COMMAND.read_text(encoding="utf-8")
    crypto=CRYPTO.read_text(encoding="utf-8")
    assert "<time dateTime={parsed.toISOString()}>{ago(value)}</time>" in command
    assert "<time dateTime={new Date(lastRefreshAt).toISOString()}>{ageLabel(lastRefreshAt,now)}</time>" in crypto

def test_e116_runtime_and_authority_contracts_preserved():
    command=COMMAND.read_text(encoding="utf-8")
    evidence=EVIDENCE.read_text(encoding="utf-8")
    surfaces=SURFACES.read_text(encoding="utf-8")
    assert "/api/live" in command and "}, 8000);" in command
    assert "/api/validation/challengers/research-evidence" in evidence and "setInterval(load,15000)" in evidence
    assert "Automatic real-money execution:" in evidence
    assert "Trading authority stays gated unless a separate validated roadmap execution explicitly unlocks it." in surfaces
