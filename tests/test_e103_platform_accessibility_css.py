from pathlib import Path

CSS=Path("frontend/src/app/globals.css")
SKIP=Path("frontend/src/app/components/SkipNavigation.tsx")
NAV=Path("frontend/src/app/components/SurfaceNavLink.tsx")
COMMAND=Path("frontend/src/app/page.tsx")
EVIDENCE=Path("frontend/src/app/research/page.tsx")
SURFACES=Path("frontend/src/app/research/surfaces/page.tsx")

def test_e103_text_selection_is_visible_and_not_disabled():
    text=CSS.read_text(encoding="utf-8")
    assert "::selection {" in text
    assert "background: #164e63;" in text
    assert "color: #ecfeff;" in text
    assert "user-select: none" not in text

def test_e103_reduced_motion_preference_collapses_shared_motion():
    text=CSS.read_text(encoding="utf-8")
    assert "@media (prefers-reduced-motion: reduce)" in text
    assert "animation-duration: 0.01ms !important;" in text
    assert "animation-iteration-count: 1 !important;" in text
    assert "transition-duration: 0.01ms !important;" in text
    assert "scroll-behavior: auto !important;" in text

def test_e103_existing_normal_motion_affordances_remain_present():
    assert "transition-transform" in SKIP.read_text(encoding="utf-8")
    assert "transition-colors" in NAV.read_text(encoding="utf-8")

def test_e103_global_accessibility_css_does_not_change_document_palette():
    text=CSS.read_text(encoding="utf-8")
    assert "background: #07080b;" in text
    assert "color: #e4e4e7;" in text
    assert "font-family: Inter, ui-sans-serif, system-ui, sans-serif;" in text

def test_e103_platform_accessibility_preserves_runtime_and_authority_boundaries():
    command=COMMAND.read_text(encoding="utf-8"); evidence=EVIDENCE.read_text(encoding="utf-8"); surfaces=SURFACES.read_text(encoding="utf-8")
    assert "/api/live" in command and "}, 8000);" in command
    assert "/api/validation/challengers/research-evidence" in evidence and "setInterval(load,15000)" in evidence
    assert "Automatic real-money execution:" in evidence
    assert "Trading authority stays gated unless a separate validated roadmap execution explicitly unlocks it." in surfaces
