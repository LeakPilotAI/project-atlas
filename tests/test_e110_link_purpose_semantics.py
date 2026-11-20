from pathlib import Path

CARDS=Path("frontend/src/app/research/surfaces/SurfaceCards.tsx")
SURFACES=Path("frontend/src/app/research/surfaces/page.tsx")
COMMAND=Path("frontend/src/app/page.tsx")
CRYPTO=Path("frontend/src/app/components/CryptoQualityDipsStatusPanel.tsx")
EVIDENCE=Path("frontend/src/app/research/page.tsx")
LAYOUT=Path("frontend/src/app/layout.tsx")

def test_e110_repeated_surface_link_has_contextual_accessible_name():
    text=CARDS.read_text(encoding="utf-8")
    assert 'aria-label={`Open ${surface.title} read-only surface`}' in text

def test_e110_visible_surface_link_copy_and_destination_remain_unchanged():
    text=CARDS.read_text(encoding="utf-8")
    assert 'href={surface.href}' in text
    assert '>Open read-only surface →</Link>' in text

def test_e110_research_navigation_labels_remain_named_and_purposeful():
    text=SURFACES.read_text(encoding="utf-8")
    assert '<nav className="flex flex-wrap gap-2" aria-label="Research navigation">' in text
    assert '<SurfaceNavLink href="/research" variant="primary">Forward Evidence</SurfaceNavLink>' in text
    assert '<SurfaceNavLink href="/">Command Center</SurfaceNavLink>' in text

def test_e110_persistent_navigation_keeps_unique_forward_evidence_purpose():
    text=LAYOUT.read_text(encoding="utf-8")
    assert '<nav aria-label="Atlas research navigation"' in text
    assert 'href="/research"' in text
    assert 'Research Evidence' in text

def test_e110_link_purpose_hardening_preserves_runtime_and_boundary_contracts():
    command=COMMAND.read_text(encoding="utf-8"); crypto=CRYPTO.read_text(encoding="utf-8"); evidence=EVIDENCE.read_text(encoding="utf-8"); surfaces=SURFACES.read_text(encoding="utf-8")
    assert "/api/live" in command and "}, 8000);" in command
    assert 'REFRESH_MS=15000;' in crypto
    assert "/api/validation/challengers/research-evidence" in evidence and "setInterval(load,15000)" in evidence
    assert "Automatic real-money execution:" in evidence
    assert "Trading authority stays gated unless a separate validated roadmap execution explicitly unlocks it." in surfaces
