from pathlib import Path

COMMAND=Path("frontend/src/app/page.tsx")
CRYPTO=Path("frontend/src/app/components/CryptoQualityDipsStatusPanel.tsx")
EVIDENCE=Path("frontend/src/app/research/page.tsx")
SURFACES=Path("frontend/src/app/research/surfaces/page.tsx")

def test_e105_command_funnel_bars_expose_named_value_semantics():
    text=COMMAND.read_text(encoding="utf-8")
    assert 'role="progressbar" aria-label={`${s.label}: ${val} of ${maxFunnel}`}' in text
    assert 'aria-valuemin={0} aria-valuemax={maxFunnel} aria-valuenow={val}' in text
    assert 'style={{ height: hgt }}' in text

def test_e105_crypto_valid_fraction_exposes_percent_value_semantics():
    text=CRYPTO.read_text(encoding="utf-8")
    assert 'role="progressbar" aria-label="Valid evidence fraction"' in text
    assert 'aria-valuemin={0} aria-valuemax={100} aria-valuenow={validPct}' in text
    assert 'style={{width:`${validPct}%`}}' in text

def test_e105_forward_progress_exposes_named_percent_value_semantics():
    text=EVIDENCE.read_text(encoding="utf-8")
    assert 'role="progressbar" aria-label={`${name} 100-close progress`}' in text
    assert 'aria-valuemin={0} aria-valuemax={100}' in text
    assert 'aria-valuenow={Math.round(Math.min(1,Number(row.closed_progress||0))*100)}' in text

def test_e105_existing_text_statuses_remain_textual_not_color_only():
    command=COMMAND.read_text(encoding="utf-8"); crypto=CRYPTO.read_text(encoding="utf-8")
    assert '{label} {on ? "on" : "off"}' in command
    assert 'Operator attention: {vm.operatorAttentionRequired?"REQUIRED":"not required"}' in crypto
    assert 'AUTHORITY LOCKED · READ ONLY' in crypto

def test_e105_visual_semantics_preserve_refresh_and_boundary_contracts():
    command=COMMAND.read_text(encoding="utf-8"); crypto=CRYPTO.read_text(encoding="utf-8"); evidence=EVIDENCE.read_text(encoding="utf-8"); surfaces=SURFACES.read_text(encoding="utf-8")
    assert "/api/live" in command and "}, 8000);" in command
    assert 'REFRESH_MS=15000;' in crypto
    assert "/api/validation/challengers/research-evidence" in evidence and "setInterval(load,15000)" in evidence
    assert "Trading authority stays gated unless a separate validated roadmap execution explicitly unlocks it." in surfaces
