from pathlib import Path

BADGE=Path("frontend/src/app/components/SurfaceStatusBadge.tsx")
OVERVIEW=Path("frontend/src/app/research/surfaces/page.tsx")
CARDS=Path("frontend/src/app/research/surfaces/SurfaceCards.tsx")
CATALOG=Path("frontend/src/app/research/surfaces/catalog.ts")

def test_e78_status_vocabulary_is_frozen_and_explicit():
    text=BADGE.read_text(encoding="utf-8")
    for key,label in (
        ("ACTIVE_EVIDENCE","ACTIVE EVIDENCE"),
        ("RESEARCH_ONLY","RESEARCH ONLY"),
        ("OPERATIONAL_VIEW","OPERATIONAL VIEW"),
        ("GATED","GATED"),
    ):
        assert f'{key}: {{ label: "{label}"' in text
    assert "production promotion remains gated" in text
    assert "no trading authority is granted" in text
    assert "observation does not grant trading authority" in text
    assert "separate validated unlock" in text

def test_e78_primitive_is_presentation_only():
    text=BADGE.read_text(encoding="utf-8")
    for token in ("fetch(", "axios", "<button", "POST", "PUT", "PATCH", "DELETE",
                  "paperOrder", "brokerOrder", "executeTrade", "live_capital_allowed"):
        assert token not in text
    assert "data-surface-status" in text

def test_e78_overview_uses_shared_status_primitive():
    text=OVERVIEW.read_text(encoding="utf-8")+"\n"+CARDS.read_text(encoding="utf-8")+"\n"+CATALOG.read_text(encoding="utf-8")
    assert "SurfaceStatusBadge" in text
    assert 'status:"ACTIVE_EVIDENCE"' in text
    assert 'status:"RESEARCH_ONLY"' in text
    assert 'status:"OPERATIONAL_VIEW"' in text
    assert "<SurfaceStatusBadge status={surface.status}/>" in text

def test_e78_overview_keeps_read_only_authority_boundary():
    text=OVERVIEW.read_text(encoding="utf-8")+"\n"+CARDS.read_text(encoding="utf-8")+"\n"+CATALOG.read_text(encoding="utf-8")
    assert "Read-only map" in text
    assert "Trading authority stays gated" in text
    assert "Authority locked" in text
    assert "Open read-only surface" in text
