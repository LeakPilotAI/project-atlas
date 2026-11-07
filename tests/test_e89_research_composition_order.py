from pathlib import Path

PAGE=Path("frontend/src/app/research/surfaces/page.tsx")
CARDS=Path("frontend/src/app/research/surfaces/SurfaceCards.tsx")

def _page():
    return PAGE.read_text(encoding="utf-8")

def test_e89_freezes_page_level_composition_order():
    text=_page()
    markers=[
        "<header",
        'aria-labelledby="research-boundary-title"',
        'aria-labelledby="authority-legend-title"',
        'aria-labelledby="navigable-surfaces-title"',
        'aria-labelledby="gated-capabilities-title"',
        'aria-labelledby="active-evidence-title"',
    ]
    positions=[text.index(marker) for marker in markers]
    assert positions == sorted(positions)
    assert len(set(positions)) == len(markers)

def test_e89_safety_and_authority_precede_research_content():
    text=_page()
    assert text.index('aria-labelledby="research-boundary-title"') < text.index('aria-labelledby="navigable-surfaces-title"')
    assert text.index('aria-labelledby="authority-legend-title"') < text.index('aria-labelledby="navigable-surfaces-title"')
    assert text.index('aria-labelledby="authority-legend-title"') < text.index('aria-labelledby="active-evidence-title"')

def test_e89_gated_capabilities_remain_separate_before_active_evidence():
    text=_page()
    assert '<section aria-labelledby="gated-capabilities-title">' in text
    assert '<section className="rounded-2xl border border-white/8 bg-[#10131a] p-4 sm:p-5" aria-labelledby="active-evidence-title">' in text
    assert text.index('aria-labelledby="gated-capabilities-title"') < text.index('aria-labelledby="active-evidence-title"')

def test_e89_navigation_remains_in_header_and_read_only_routes_unchanged():
    text=_page()
    header=text.split("<header",1)[1].split("</header>",1)[0]
    assert 'aria-label="Research navigation"' in header
    assert '<SurfaceNavLink href="/research"' in header
    assert '<SurfaceNavLink href="/"' in header
    assert "Forward Evidence" in header
    assert "Command Center" in header

def test_e89_gated_component_remains_non_navigable():
    text=CARDS.read_text(encoding="utf-8")
    gated=text.split("export function GatedCapabilityCard",1)[1].split("function Posture",1)[0]
    assert '<SurfaceStatusBadge status="GATED"/>' in gated
    assert "<Link" not in gated
    assert "href=" not in gated
    assert "<button" not in gated

def test_e89_page_remains_static_and_action_free():
    text=_page()
    for token in ("use client", "fetch(", "axios", "useEffect", "useState", "<button",
                  'method:"POST"', 'method:"PUT"', 'method:"PATCH"', 'method:"DELETE"',
                  "paperOrder", "brokerOrder", "executeTrade", "repair_action"):
        assert token not in text
