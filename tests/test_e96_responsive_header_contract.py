from pathlib import Path

COMMAND = Path("frontend/src/app/page.tsx")
EVIDENCE = Path("frontend/src/app/research/page.tsx")
SURFACES = Path("frontend/src/app/research/surfaces/page.tsx")
IDENTITY = Path("frontend/src/app/components/PageIdentity.tsx")


def test_e96_command_center_action_cluster_wraps_without_changing_operational_frame():
    text = COMMAND.read_text(encoding="utf-8")
    assert '<div className="max-w-7xl mx-auto px-6 py-4 flex flex-wrap items-end justify-between gap-4">' in text
    assert '<div className="flex flex-wrap items-end gap-4">' in text
    assert '<header className="border-b border-white/5 bg-[#0b0d12]/90 backdrop-blur sticky top-0 z-10">' in text
    assert '<main id="main-content" tabIndex={-1} className="max-w-7xl mx-auto px-6 py-6 space-y-6">' in text
    assert "/api/live" in text
    assert "}, 8000);" in text
    assert "<CryptoQualityDipsStatusPanel />" in text


def test_e96_forward_evidence_header_and_nav_wrap_at_narrow_widths():
    text = EVIDENCE.read_text(encoding="utf-8")
    assert '<ReadOnlyPageShell layout="evidence"><header className="flex flex-wrap items-start justify-between gap-4">' in text
    assert '<nav className="flex flex-wrap gap-2" aria-label="Research navigation">' in text
    assert 'href="/research/surfaces"' in text
    assert 'href="/"' in text
    assert "/api/validation/challengers/research-evidence" in text
    assert "setInterval(load,15000)" in text
    assert "clearInterval(id)" in text


def test_e96_research_surfaces_keeps_wrapping_header_and_wraps_peer_nav():
    text = SURFACES.read_text(encoding="utf-8")
    assert '<header className="flex flex-wrap items-start justify-between gap-4">' in text
    assert '<nav className="flex flex-wrap gap-2" aria-label="Research navigation">' in text
    assert 'href="/research"' in text
    assert 'href="/"' in text
    assert "fetch(" not in text
    assert "useEffect" not in text
    assert "useState" not in text


def test_e96_responsive_changes_preserve_identity_and_safety_copy():
    command = COMMAND.read_text(encoding="utf-8")
    evidence = EVIDENCE.read_text(encoding="utf-8")
    surfaces = SURFACES.read_text(encoding="utf-8")
    assert 'description="Bot runs in the Atlas window. This page is watch-only. Discord is the alert feed."' in command
    assert 'description="Read-only durable evidence. Research progress is not production approval."' in evidence
    assert "Live capital:" in evidence
    assert "Automatic real-money execution:" in evidence
    assert "Evidence presentation does not create strategy-selection, PAPER, execution, promotion, or live-capital authority." in surfaces
    assert "Trading authority stays gated unless a separate validated roadmap execution explicitly unlocks it." in surfaces


def test_e96_does_not_expand_shared_identity_into_header_or_responsive_ownership():
    text = IDENTITY.read_text(encoding="utf-8")
    assert "flex-wrap" not in text
    assert "justify-between" not in text
    assert "<nav" not in text
    assert "<header" not in text
    assert "sticky top-0" not in text
    assert "SurfaceNavLink" not in text
