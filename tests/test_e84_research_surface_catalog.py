from pathlib import Path

PAGE=Path("frontend/src/app/research/surfaces/page.tsx")
CATALOG=Path("frontend/src/app/research/surfaces/catalog.ts")

def test_e84_page_renders_from_typed_catalog():
    page=PAGE.read_text(encoding="utf-8")
    assert 'import { GATED_CAPABILITIES, RESEARCH_SURFACES } from "./catalog";' in page
    assert "RESEARCH_SURFACES.map" in page
    assert "GATED_CAPABILITIES.map" in page
    assert "const surfaces:" not in page
    assert "const gatedCapabilities:" not in page

def test_e84_catalog_is_typed_read_only_and_runtime_frozen():
    text=CATALOG.read_text(encoding="utf-8")
    assert "export type ResearchSurfaceDefinition = Readonly<{" in text
    assert "export type GatedCapabilityDefinition = Readonly<{" in text
    assert "readonly ResearchSurfaceDefinition[]" in text
    assert "readonly GatedCapabilityDefinition[]" in text
    assert text.count("Object.freeze(") >= 9

def test_e84_catalog_preserves_surface_contracts():
    text=CATALOG.read_text(encoding="utf-8")
    for token in ('title:"Alpha / Forward Evidence"','status:"ACTIVE_EVIDENCE"','href:"/research"',
                  'title:"Crypto Quality Dips"','status:"RESEARCH_ONLY"',
                  'title:"Command Center Operations"','status:"OPERATIONAL_VIEW"',
                  "Prospective evidence · accumulated over time · no synthetic acceleration.",
                  "Authority locked · no scoring, PAPER, execution, or live capital · repair authority unavailable.",
                  "Watch-only visibility · navigation and observation do not grant trading authority."):
        assert token in text

def test_e84_catalog_preserves_gated_contracts():
    text=CATALOG.read_text(encoding="utf-8")
    for token in ("Crypto Quality Dips autonomy","INACTIVE / GATED","Alpha strategy selection",
                  "Residual trading Discord lifecycle","Automated real-money execution",
                  "dedicated lifecycle contracts rather than bulk migration",
                  "Live-capital execution remains gated"):
        assert token in text

def test_e84_catalog_and_page_remain_static_and_authority_free():
    text=PAGE.read_text(encoding="utf-8")+"\n"+CATALOG.read_text(encoding="utf-8")
    for token in ("fetch(", "axios", "useEffect", "useState", "<button", "POST", "PUT", "PATCH", "DELETE",
                  "paperOrder", "brokerOrder", "executeTrade", "repair_action"):
        assert token not in text
