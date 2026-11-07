from pathlib import Path

LAYOUT=Path("frontend/src/app/layout.tsx")
COMMAND=Path("frontend/src/app/page.tsx")
EVIDENCE=Path("frontend/src/app/research/page.tsx")
SURFACES=Path("frontend/src/app/research/surfaces/page.tsx")

def test_e100_persistent_research_navigation_keeps_semantics():
    text=LAYOUT.read_text(encoding="utf-8")
    assert '<nav aria-label="Atlas research navigation" className="fixed bottom-4 right-4 z-50">' in text
    assert '<a href="/research"' in text
    assert "Research Evidence" in text

def test_e100_persistent_research_link_has_keyboard_focus_visibility():
    text=LAYOUT.read_text(encoding="utf-8")
    for token in ("hover:border-cyan-400/40","focus:outline-none","focus-visible:border-cyan-300","focus-visible:ring-2","focus-visible:ring-cyan-300","focus-visible:ring-offset-2"):
        assert token in text

def test_e100_root_navigation_remains_static():
    text=LAYOUT.read_text(encoding="utf-8")
    assert "<SkipNavigation />" in text
    for token in ('"use client"', "onClick", "onKeyDown", "useEffect", "useState"):
        assert token not in text

def test_e100_cross_surface_destinations_remain_unchanged():
    command=COMMAND.read_text(encoding="utf-8"); evidence=EVIDENCE.read_text(encoding="utf-8"); surfaces=SURFACES.read_text(encoding="utf-8")
    assert 'href="/research/surfaces"' in command
    assert 'href="/research/surfaces"' in evidence and 'href="/"' in evidence
    assert 'href="/research"' in surfaces and 'href="/"' in surfaces

def test_e100_focus_hardening_preserves_runtime_and_authority_boundaries():
    command=COMMAND.read_text(encoding="utf-8"); evidence=EVIDENCE.read_text(encoding="utf-8"); surfaces=SURFACES.read_text(encoding="utf-8")
    assert "/api/live" in command and "}, 8000);" in command
    assert "/api/validation/challengers/research-evidence" in evidence
    assert "setInterval(load,15000)" in evidence
    assert "Automatic real-money execution:" in evidence
    assert "Trading authority stays gated unless a separate validated roadmap execution explicitly unlocks it." in surfaces
