from pathlib import Path

LINK=Path("frontend/src/app/components/SurfaceNavLink.tsx")
COMMAND=Path("frontend/src/app/page.tsx")
EVIDENCE=Path("frontend/src/app/research/page.tsx")
SURFACES=Path("frontend/src/app/research/surfaces/page.tsx")


def test_e98_shared_surface_nav_link_has_explicit_keyboard_focus_visibility():
    text=LINK.read_text(encoding="utf-8")
    for token in ("focus-visible:outline-none","focus-visible:ring-2","focus-visible:ring-cyan-300","focus-visible:ring-offset-2","focus-visible:ring-offset-[#07080b]"):
        assert token in text


def test_e98_focus_contract_is_shared_by_both_existing_link_variants():
    text=LINK.read_text(encoding="utf-8")
    assert "const INTERACTION_CLASS =" in text
    assert "primary: `rounded-lg border border-cyan-500/20 px-3 py-2 text-xs text-cyan-300 ${INTERACTION_CLASS}`" in text
    assert "secondary: `rounded-lg border border-white/10 px-3 py-2 text-xs text-zinc-400 ${INTERACTION_CLASS}`" in text


def test_e98_surface_nav_link_remains_a_plain_next_link_without_event_logic():
    text=LINK.read_text(encoding="utf-8")
    assert 'import Link from "next/link";' in text
    assert "return <Link href={href} className={VARIANT_CLASS[variant]}>{children}</Link>;" in text
    for token in ("use client","onClick","onKeyDown","tabIndex","useState","useEffect","fetch("):
        assert token not in text


def test_e98_cross_surface_destinations_and_named_navigation_remain_unchanged():
    command=COMMAND.read_text(encoding="utf-8"); evidence=EVIDENCE.read_text(encoding="utf-8"); surfaces=SURFACES.read_text(encoding="utf-8")
    assert '<nav aria-label="Research navigation"><SurfaceNavLink href="/research/surfaces" variant="primary">Research Surfaces</SurfaceNavLink></nav>' in command
    assert '<SurfaceNavLink href="/research/surfaces" variant="primary">Research Surfaces</SurfaceNavLink><SurfaceNavLink href="/">Command Center</SurfaceNavLink>' in evidence
    assert '<SurfaceNavLink href="/research" variant="primary">Forward Evidence</SurfaceNavLink><SurfaceNavLink href="/">Command Center</SurfaceNavLink>' in surfaces


def test_e98_focus_polish_preserves_runtime_and_authority_boundaries():
    command=COMMAND.read_text(encoding="utf-8"); evidence=EVIDENCE.read_text(encoding="utf-8"); surfaces=SURFACES.read_text(encoding="utf-8")
    assert "/api/live" in command and "}, 8000);" in command and "<CryptoQualityDipsStatusPanel />" in command
    assert "/api/validation/challengers/research-evidence" in evidence
    assert "setInterval(load,15000)" in evidence and "clearInterval(id)" in evidence
    assert "Automatic real-money execution:" in evidence
    assert "Trading authority stays gated unless a separate validated roadmap execution explicitly unlocks it." in surfaces
