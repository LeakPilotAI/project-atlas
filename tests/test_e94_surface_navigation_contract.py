from pathlib import Path

COMMAND = Path("frontend/src/app/page.tsx")
EVIDENCE = Path("frontend/src/app/research/page.tsx")
SURFACES = Path("frontend/src/app/research/surfaces/page.tsx")
NAV = Path("frontend/src/app/components/SurfaceNavLink.tsx")


def test_e94_shared_nav_link_is_pure_static_presentation():
    text = NAV.read_text(encoding="utf-8")
    assert 'import Link from "next/link";' in text
    assert "primary: `rounded-lg border border-cyan-500/20 px-3 py-2 text-xs text-cyan-300 ${INTERACTION_CLASS}`" in text
    assert "secondary: `rounded-lg border border-white/10 px-3 py-2 text-xs text-zinc-400 ${INTERACTION_CLASS}`" in text
    assert "const INTERACTION_CLASS =" in text
    assert "VARIANT_CLASS[variant]" in text
    for token in ('"use client"', "fetch(", "useEffect", "useState", "<button", "API"):
        assert token not in text


def test_e94_command_center_keeps_bounded_hub_navigation_and_runtime():
    text = COMMAND.read_text(encoding="utf-8")
    assert '<SurfaceNavLink href="/research/surfaces" variant="primary">Research Surfaces</SurfaceNavLink>' in text
    assert '<SurfaceNavLink href="/research"' not in text
    assert 'const API = "http://127.0.0.1:8000";' in text
    assert "/api/live" in text
    assert "}, 8000);" in text
    assert "clearInterval(id);" in text
    assert "<CryptoQualityDipsStatusPanel />" in text


def test_e94_forward_evidence_navigation_is_accessible_and_routes_unchanged():
    text = EVIDENCE.read_text(encoding="utf-8")
    assert 'aria-label="Research navigation"' in text
    assert '<SurfaceNavLink href="/research/surfaces" variant="primary">Research Surfaces</SurfaceNavLink>' in text
    assert '<SurfaceNavLink href="/">Command Center</SurfaceNavLink>' in text
    assert "/api/validation/challengers/research-evidence" in text
    assert "setInterval(load,15000)" in text
    assert "clearInterval(id)" in text
    assert "Atlas remains NOT READY by default." in text


def test_e94_research_surfaces_navigation_is_accessible_and_routes_unchanged():
    text = SURFACES.read_text(encoding="utf-8")
    assert 'aria-label="Research navigation"' in text
    assert '<SurfaceNavLink href="/research" variant="primary">Forward Evidence</SurfaceNavLink>' in text
    assert '<SurfaceNavLink href="/">Command Center</SurfaceNavLink>' in text
    assert "fetch(" not in text
    assert "useEffect" not in text
    assert "useState" not in text


def test_e94_navigation_extraction_does_not_change_authority_boundaries():
    command = COMMAND.read_text(encoding="utf-8")
    evidence = EVIDENCE.read_text(encoding="utf-8")
    surfaces = SURFACES.read_text(encoding="utf-8")
    assert "This page is watch-only." in command
    assert "Research progress is not production approval." in evidence
    assert "Live capital:" in evidence
    assert "Automatic real-money execution:" in evidence
    assert "Trading authority stays gated unless a separate validated roadmap execution explicitly unlocks it." in surfaces
