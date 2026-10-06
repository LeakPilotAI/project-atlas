from pathlib import Path

OVERVIEW=Path("frontend/src/app/research/surfaces/page.tsx")
PRESENTATION=Path("frontend/src/app/research/surfaces/presentation.ts")
CATALOG=Path("frontend/src/app/research/surfaces/catalog.ts")

def test_e81_separates_navigable_surfaces_from_gated_capabilities():
    text=OVERVIEW.read_text(encoding="utf-8")+"\n"+PRESENTATION.read_text(encoding="utf-8")+"\n"+CATALOG.read_text(encoding="utf-8")
    assert 'id="navigable-surfaces-title"' in text
    assert ">Current navigable surfaces</h2>" in text
    assert 'id="gated-capabilities-title"' in text
    assert ">Gated roadmap capabilities</h2>" in text
    assert "These are not destinations or disabled controls." in text

def test_e81_gated_items_are_roadmap_confirmed():
    text=OVERVIEW.read_text(encoding="utf-8")+"\n"+PRESENTATION.read_text(encoding="utf-8")+"\n"+CATALOG.read_text(encoding="utf-8")
    for title in ("Crypto Quality Dips autonomy","Alpha strategy selection","Residual trading Discord lifecycle","Automated real-money execution"):
        assert title in text
    assert "no synthetic acceleration" in text
    assert "dedicated lifecycle contracts rather than bulk migration" in text

def test_e81_gated_items_reuse_canonical_status_and_are_non_clickable():
    text=OVERVIEW.read_text(encoding="utf-8")+"\n"+PRESENTATION.read_text(encoding="utf-8")+"\n"+CATALOG.read_text(encoding="utf-8")
    assert 'GATED_CAPABILITIES.map' in text
    assert '<SurfaceStatusBadge status="GATED"/>' in text
    gated_section=text.split('aria-labelledby="gated-capabilities-title"',1)[1].split('Current roadmap state',1)[0]
    assert "<Link" not in gated_section
    assert 'href=' not in gated_section
    assert "<button" not in gated_section

def test_e81_existing_navigable_surface_contracts_remain():
    text=OVERVIEW.read_text(encoding="utf-8")+"\n"+PRESENTATION.read_text(encoding="utf-8")+"\n"+CATALOG.read_text(encoding="utf-8")
    assert 'href:"/research"' in text
    assert text.count('href:"/"') == 2
    assert "Open read-only surface" in text
    assert 'status:"ACTIVE_EVIDENCE"' in text
    assert 'status:"RESEARCH_ONLY"' in text
    assert 'status:"OPERATIONAL_VIEW"' in text

def test_e81_page_remains_static_and_action_free():
    text=OVERVIEW.read_text(encoding="utf-8")+"\n"+PRESENTATION.read_text(encoding="utf-8")+"\n"+CATALOG.read_text(encoding="utf-8")
    for token in ("fetch(", "axios", "useEffect", "useState", "<button", "method:\"POST\"", "method:\"PUT\"", "method:\"PATCH\"", "method:\"DELETE\"",
                  "paperOrder", "brokerOrder", "executeTrade", "repair_action"):
        assert token not in text
