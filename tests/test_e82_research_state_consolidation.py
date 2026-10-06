from pathlib import Path

OVERVIEW=Path("frontend/src/app/research/surfaces/page.tsx")

def test_e82_active_evidence_has_dedicated_static_section():
    text=OVERVIEW.read_text(encoding="utf-8")
    assert 'aria-labelledby="active-evidence-title"' in text
    assert 'id="active-evidence-title"' in text
    assert ">Active evidence collection</h2>" in text
    assert "Genuine evidence accumulation currently in progress." in text
    assert "Gated capabilities are listed separately above." in text

def test_e82_preserves_only_confirmed_active_context_in_active_section():
    text=OVERVIEW.read_text(encoding="utf-8")
    active=text.split('aria-labelledby="active-evidence-title"',1)[1].split("</section>",1)[0]
    assert "E29 forward strategy evidence" in active
    assert "ACTIVE · genuine evidence only" in active
    assert "Alpha / cadence / corroboration" in active
    assert "ACTIVE · strategy selection gated" in active
    assert "Crypto Quality Dips autonomy" not in active
    assert "Residual trading Discord lifecycle" not in active

def test_e82_gated_section_is_canonical_for_gated_capabilities():
    text=OVERVIEW.read_text(encoding="utf-8")
    gated_data=text.split("const gatedCapabilities",1)[1].split("export default",1)[0]
    gated_section=text.split('aria-labelledby="gated-capabilities-title"',1)[1].split('aria-labelledby="active-evidence-title"',1)[0]
    for title in ("Crypto Quality Dips autonomy","Alpha strategy selection","Residual trading Discord lifecycle","Automated real-money execution"):
        assert title in gated_data
    assert '<SurfaceStatusBadge status="GATED"/>' in gated_section
    assert "<Link" not in gated_section and "href=" not in gated_section and "<button" not in gated_section

def test_e82_removes_legacy_duplicate_roadmap_state_block():
    text=OVERVIEW.read_text(encoding="utf-8")
    assert "Current roadmap state" not in text
    assert 'value="INACTIVE / GATED"' not in text
    assert 'label="Residual trading Discord lifecycle" value="GATED"' not in text

def test_e82_page_remains_static_read_only_and_action_free():
    text=OVERVIEW.read_text(encoding="utf-8")
    for token in ("fetch(", "axios", "useEffect", "useState", "<button", "POST", "PUT", "PATCH", "DELETE",
                  "paperOrder", "brokerOrder", "executeTrade", "repair_action"):
        assert token not in text
