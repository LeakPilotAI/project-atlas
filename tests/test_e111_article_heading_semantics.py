from pathlib import Path

CARDS=Path("frontend/src/app/research/surfaces/SurfaceCards.tsx")
SURFACES=Path("frontend/src/app/research/surfaces/page.tsx")
COMMAND=Path("frontend/src/app/page.tsx")
CRYPTO=Path("frontend/src/app/components/CryptoQualityDipsStatusPanel.tsx")
EVIDENCE=Path("frontend/src/app/research/page.tsx")

def test_e111_research_surface_article_is_named_by_visible_heading():
    text=CARDS.read_text(encoding="utf-8")
    assert 'const headingId=`research-surface-${surface.title.toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"")}`;' in text
    assert '<article aria-labelledby={headingId}' in text
    assert '<h2 id={headingId}' in text

def test_e111_gated_capability_article_is_named_by_visible_heading():
    text=CARDS.read_text(encoding="utf-8")
    assert 'const headingId=`gated-capability-${capability.title.toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"")}`;' in text
    assert '<h3 id={headingId}' in text

def test_e111_article_heading_hardening_preserves_card_content_and_link_purpose():
    text=CARDS.read_text(encoding="utf-8")
    assert '<SurfaceStatusBadge status={surface.status}/>' in text
    assert '<Posture label="Purpose" value={surface.purpose}/>' in text
    assert 'aria-label={`Open ${surface.title} read-only surface`}' in text
    assert '>Open read-only surface →</Link>' in text
    assert '<SurfaceStatusBadge status="GATED"/>' in text
    assert '{capability.detail}' in text

def test_e111_forward_candidate_articles_keep_existing_accessible_names():
    text=EVIDENCE.read_text(encoding="utf-8")
    assert '<article aria-label={name}' in text
    assert '<span className="font-medium text-white">{name}</span>' in text

def test_e111_article_heading_hardening_preserves_runtime_and_boundary_contracts():
    command=COMMAND.read_text(encoding="utf-8"); crypto=CRYPTO.read_text(encoding="utf-8"); evidence=EVIDENCE.read_text(encoding="utf-8"); surfaces=SURFACES.read_text(encoding="utf-8")
    assert "/api/live" in command and "}, 8000);" in command
    assert 'REFRESH_MS=15000;' in crypto
    assert "/api/validation/challengers/research-evidence" in evidence and "setInterval(load,15000)" in evidence
    assert "Automatic real-money execution:" in evidence
    assert "Trading authority stays gated unless a separate validated roadmap execution explicitly unlocks it." in surfaces
