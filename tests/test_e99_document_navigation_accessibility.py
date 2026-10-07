from pathlib import Path

SKIP=Path("frontend/src/app/components/SkipNavigation.tsx")
LAYOUT=Path("frontend/src/app/layout.tsx")
COMMAND=Path("frontend/src/app/page.tsx")
SHELL=Path("frontend/src/app/components/ReadOnlyPageShell.tsx")
EVIDENCE=Path("frontend/src/app/research/page.tsx")
SURFACES=Path("frontend/src/app/research/surfaces/page.tsx")


def test_e99_root_layout_exposes_one_shared_static_skip_navigation_link():
    skip=SKIP.read_text(encoding="utf-8"); layout=LAYOUT.read_text(encoding="utf-8")
    assert 'href="#main-content"' in skip
    assert "Skip to main content" in skip
    assert 'import { SkipNavigation } from "@/app/components/SkipNavigation";' in layout
    assert "<SkipNavigation />" in layout
    for token in ("use client", "onClick", "onKeyDown", "useState", "useEffect", "fetch("):
        assert token not in skip


def test_e99_skip_navigation_is_hidden_until_keyboard_focus_and_visibly_focused():
    text=SKIP.read_text(encoding="utf-8")
    for token in ("-translate-y-24", "focus:translate-y-0", "focus:outline-none", "focus-visible:ring-2", "focus-visible:ring-cyan-300"):
        assert token in text


def test_e99_all_established_surfaces_have_the_same_stable_main_target():
    command=COMMAND.read_text(encoding="utf-8"); shell=SHELL.read_text(encoding="utf-8")
    assert '<main id="main-content" tabIndex={-1} className="max-w-7xl mx-auto px-6 py-6 space-y-6">' in command
    assert '<main id="main-content" tabIndex={-1} className={LAYOUT_CLASS[layout]}>{children}</main>' in shell
    assert shell.count('id="main-content"') == 1


def test_e99_cross_surface_navigation_destinations_remain_unchanged():
    command=COMMAND.read_text(encoding="utf-8"); evidence=EVIDENCE.read_text(encoding="utf-8"); surfaces=SURFACES.read_text(encoding="utf-8")
    assert '<SurfaceNavLink href="/research/surfaces" variant="primary">Research Surfaces</SurfaceNavLink>' in command
    assert '<SurfaceNavLink href="/research/surfaces" variant="primary">Research Surfaces</SurfaceNavLink><SurfaceNavLink href="/">Command Center</SurfaceNavLink>' in evidence
    assert '<SurfaceNavLink href="/research" variant="primary">Forward Evidence</SurfaceNavLink><SurfaceNavLink href="/">Command Center</SurfaceNavLink>' in surfaces


def test_e99_document_navigation_preserves_runtime_and_authority_boundaries():
    command=COMMAND.read_text(encoding="utf-8"); evidence=EVIDENCE.read_text(encoding="utf-8"); surfaces=SURFACES.read_text(encoding="utf-8")
    assert "/api/live" in command and "}, 8000);" in command and "<CryptoQualityDipsStatusPanel />" in command
    assert "/api/validation/challengers/research-evidence" in evidence
    assert "setInterval(load,15000)" in evidence and "clearInterval(id)" in evidence
    assert "Automatic real-money execution:" in evidence
    assert "Trading authority stays gated unless a separate validated roadmap execution explicitly unlocks it." in surfaces
