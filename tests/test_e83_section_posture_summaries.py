from pathlib import Path

OVERVIEW=Path("frontend/src/app/research/surfaces/page.tsx")

def test_e83_navigable_section_summary_is_purpose_and_authority_only():
    text=OVERVIEW.read_text(encoding="utf-8")
    assert "Purpose: open established read-only operator and research views." in text
    assert "Authority: navigation and observation do not grant trading authority." in text

def test_e83_gated_section_summary_is_purpose_and_authority_only():
    text=OVERVIEW.read_text(encoding="utf-8")
    assert "Purpose: show roadmap-confirmed unavailable capabilities for operator context." in text
    assert "Authority: gated items are not destinations, controls, or readiness claims." in text

def test_e83_active_section_summary_does_not_imply_unlock():
    text=OVERVIEW.read_text(encoding="utf-8")
    assert "Purpose: show genuine evidence accumulation currently in progress." in text
    assert "Authority: active evidence does not unlock strategy selection, promotion, PAPER, or execution." in text

def test_e83_summaries_preserve_existing_hierarchy_and_status_vocabulary():
    text=OVERVIEW.read_text(encoding="utf-8")
    for heading in ("Current navigable surfaces","Gated roadmap capabilities","Active evidence collection"):
        assert heading in text
    assert '<SurfaceStatusBadge status="GATED"/>' in text
    assert 'status:"ACTIVE_EVIDENCE"' in text
    assert 'status:"RESEARCH_ONLY"' in text
    assert 'status:"OPERATIONAL_VIEW"' in text

def test_e83_page_remains_static_without_dynamic_summary_claims():
    text=OVERVIEW.read_text(encoding="utf-8")
    for token in ("fetch(", "axios", "useEffect", "useState", "<button", "POST", "PUT", "PATCH", "DELETE",
                  "paperOrder", "brokerOrder", "executeTrade", "repair_action"):
        assert token not in text
    for phrase in ("ready now","ready for production","percent ready","readiness score"):
        assert phrase not in text.lower()
