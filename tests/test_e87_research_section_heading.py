from pathlib import Path

PAGE=Path("frontend/src/app/research/surfaces/page.tsx")
HEADING=Path("frontend/src/app/research/surfaces/SectionHeading.tsx")
PRESENTATION=Path("frontend/src/app/research/surfaces/presentation.ts")

def test_e87_page_uses_section_heading_for_repeated_sections():
    text=PAGE.read_text(encoding="utf-8")
    assert 'import { SectionHeading } from "./SectionHeading";' in text
    assert '<SectionHeading id="navigable-surfaces-title" title="Current navigable surfaces" posture={SECTION_POSTURE.navigable}/>' in text
    assert '<SectionHeading id="gated-capabilities-title" title="Gated roadmap capabilities" posture={SECTION_POSTURE.gated}/>' in text

def test_e87_section_heading_preserves_css_and_heading_semantics():
    text=HEADING.read_text(encoding="utf-8")
    assert 'className="mb-3"' in text
    assert '<h2 id={id} className="text-sm font-medium text-zinc-300">{title}</h2>' in text
    assert '<p className="mt-1 text-xs text-zinc-600">{posture}</p>' in text

def test_e87_page_preserves_aria_labelledby_relationships():
    text=PAGE.read_text(encoding="utf-8")
    assert '<section aria-labelledby="navigable-surfaces-title">' in text
    assert 'id="navigable-surfaces-title"' in text
    assert '<section aria-labelledby="gated-capabilities-title">' in text
    assert 'id="gated-capabilities-title"' in text

def test_e87_visible_heading_and_posture_contracts_remain():
    page=PAGE.read_text(encoding="utf-8")
    presentation=PRESENTATION.read_text(encoding="utf-8")
    assert "Current navigable surfaces" in page
    assert "Gated roadmap capabilities" in page
    assert "Purpose: open established read-only operator and research views." in presentation
    assert "Purpose: show roadmap-confirmed unavailable capabilities for operator context." in presentation

def test_e87_section_heading_is_pure_static_and_authority_free():
    text=HEADING.read_text(encoding="utf-8")
    for token in ("use client", "fetch(", "axios", "useEffect", "useState", "<button", "<Link",
                  'method:"POST"', 'method:"PUT"', 'method:"PATCH"', 'method:"DELETE"',
                  "paperOrder", "brokerOrder", "executeTrade", "repair_action"):
        assert token not in text
