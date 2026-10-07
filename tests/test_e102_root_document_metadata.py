from pathlib import Path

ROOT=Path("frontend/src/app/layout.tsx")
CSS=Path("frontend/src/app/globals.css")
COMMAND=Path("frontend/src/app/page.tsx")
EVIDENCE=Path("frontend/src/app/research/page.tsx")
SURFACES=Path("frontend/src/app/research/surfaces/page.tsx")

def test_e102_root_exports_typed_responsive_viewport():
    text=ROOT.read_text(encoding="utf-8")
    assert 'import type { Metadata, Viewport } from "next";' in text
    assert "export const viewport: Viewport = {" in text
    assert 'width: "device-width"' in text
    assert "initialScale: 1" in text

def test_e102_root_declares_dark_browser_color_semantics_matching_document_palette():
    root=ROOT.read_text(encoding="utf-8"); css=CSS.read_text(encoding="utf-8")
    assert 'colorScheme: "dark"' in root
    assert 'themeColor: "#07080b"' in root
    assert "background: #07080b;" in css

def test_e102_viewport_does_not_disable_user_zoom():
    text=ROOT.read_text(encoding="utf-8")
    assert "maximumScale" not in text
    assert "userScalable" not in text

def test_e102_root_document_semantics_and_navigation_remain_intact():
    text=ROOT.read_text(encoding="utf-8")
    assert '<html lang="en" suppressHydrationWarning>' in text
    assert "<SkipNavigation />" in text
    assert '<nav aria-label="Atlas research navigation" className="fixed bottom-4 right-4 z-50">' in text
    assert '<a href="/research"' in text

def test_e102_platform_metadata_preserves_runtime_and_authority_boundaries():
    command=COMMAND.read_text(encoding="utf-8"); evidence=EVIDENCE.read_text(encoding="utf-8"); surfaces=SURFACES.read_text(encoding="utf-8")
    assert "/api/live" in command and "}, 8000);" in command
    assert "/api/validation/challengers/research-evidence" in evidence and "setInterval(load,15000)" in evidence
    assert "Automatic real-money execution:" in evidence
    assert "Trading authority stays gated unless a separate validated roadmap execution explicitly unlocks it." in surfaces
