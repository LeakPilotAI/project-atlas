from pathlib import Path

COMMAND = Path("frontend/src/app/page.tsx")
EVIDENCE = Path("frontend/src/app/research/page.tsx")
SURFACES = Path("frontend/src/app/research/surfaces/page.tsx")
IDENTITY = Path("frontend/src/app/components/PageIdentity.tsx")


def test_e95_page_identity_is_pure_static_presentation():
    text = IDENTITY.read_text(encoding="utf-8")
    assert "export function PageIdentity" in text
    assert 'operational: "text-[11px] uppercase tracking-[0.22em] text-emerald-500/80"' in text
    assert 'research: "text-[11px] uppercase tracking-[0.22em] text-cyan-400/80"' in text
    assert '<h1 className="mt-1 text-2xl font-semibold tracking-tight text-white">{title}</h1>' in text
    for token in ('"use client"', "fetch(", "useEffect", "useState", "<nav", "<header", "<button", "href="):
        assert token not in text


def test_e95_command_center_adopts_identity_without_frame_or_runtime_change():
    text = COMMAND.read_text(encoding="utf-8")
    assert '<PageIdentity' in text
    assert 'eyebrow="Live command center"' in text
    assert 'title="Project Atlas"' in text
    assert 'tone="operational"' in text
    assert 'description="Bot runs in the Atlas window. This page is watch-only. Discord is the alert feed."' in text
    assert '<header className="border-b border-white/5 bg-[#0b0d12]/90 backdrop-blur sticky top-0 z-10">' in text
    assert '<main className="max-w-7xl mx-auto px-6 py-6 space-y-6">' in text
    assert "/api/live" in text
    assert "}, 8000);" in text
    assert "clearInterval(id);" in text
    assert "<CryptoQualityDipsStatusPanel />" in text


def test_e95_forward_evidence_adopts_identity_without_runtime_or_authority_change():
    text = EVIDENCE.read_text(encoding="utf-8")
    assert '<PageIdentity eyebrow="V6 research evidence" title="Forward Evidence Panel"' in text
    assert 'description="Read-only durable evidence. Research progress is not production approval."' in text
    assert 'aria-label="Research navigation"' in text
    assert "/api/validation/challengers/research-evidence" in text
    assert "setInterval(load,15000)" in text
    assert "clearInterval(id)" in text
    assert "Live capital:" in text
    assert "Automatic real-money execution:" in text


def test_e95_research_surfaces_adopts_identity_without_static_boundary_change():
    text = SURFACES.read_text(encoding="utf-8")
    assert '<PageIdentity eyebrow="Atlas research architecture" title="Research Surfaces"' in text
    assert 'constrainDescription/>' in text
    assert "Evidence presentation does not create strategy-selection, PAPER, execution, promotion, or live-capital authority." in text
    assert 'aria-label="Research navigation"' in text
    assert "Trading authority stays gated unless a separate validated roadmap execution explicitly unlocks it." in text
    assert "fetch(" not in text
    assert "useEffect" not in text
    assert "useState" not in text


def test_e95_identity_extraction_does_not_own_layout_navigation_or_authority():
    identity = IDENTITY.read_text(encoding="utf-8")
    command = COMMAND.read_text(encoding="utf-8")
    evidence = EVIDENCE.read_text(encoding="utf-8")
    surfaces = SURFACES.read_text(encoding="utf-8")
    assert "sticky top-0" not in identity
    assert "max-w-7xl" not in identity
    assert "SurfaceNavLink" not in identity
    assert "ReadOnlyPageShell" not in identity
    assert "sticky top-0" in command
    assert 'ReadOnlyPageShell layout="evidence"' in evidence
    assert "<ReadOnlyPageShell>" in surfaces
