from pathlib import Path

OVERVIEW=Path("frontend/src/app/research/surfaces/page.tsx")
PRESENTATION=Path("frontend/src/app/research/surfaces/presentation.ts")
BADGE=Path("frontend/src/app/components/SurfaceStatusBadge.tsx")

def test_e80_authority_legend_is_accessible_and_static():
    text=OVERVIEW.read_text(encoding="utf-8")+"\n"+PRESENTATION.read_text(encoding="utf-8")
    assert 'aria-labelledby="authority-legend-title"' in text
    assert 'id="authority-legend-title"' in text
    assert ">Authority legend</h2>" in text
    assert "<dl" in text and "<dt" in text and "<dd" in text
    assert "function Legend(" in text

def test_e80_legend_explains_existing_authority_semantics():
    text=OVERVIEW.read_text(encoding="utf-8")+"\n"+PRESENTATION.read_text(encoding="utf-8")
    assert 'Read-only presentation' in text
    assert "viewing it grants no trading authority" in text
    assert 'Human-review-only evidence' in text
    assert "strategy selection and production promotion remain gated" in text
    assert 'Gated capability' in text
    assert "separate validated roadmap unlock" in text

def test_e80_legend_does_not_conflict_with_e78_vocabulary():
    overview=OVERVIEW.read_text(encoding="utf-8")
    badge=BADGE.read_text(encoding="utf-8")
    for label in ("ACTIVE EVIDENCE","RESEARCH ONLY","OPERATIONAL VIEW","GATED"):
        assert label in badge
    assert "SurfaceStatusBadge" in overview
    assert "Authority legend" in overview

def test_e80_legend_adds_no_live_or_action_authority():
    text=OVERVIEW.read_text(encoding="utf-8")+"\n"+PRESENTATION.read_text(encoding="utf-8")
    for token in ("fetch(", "axios", "useEffect", "useState", "<button", "method:\"POST\"", "method:\"PUT\"", "method:\"PATCH\"", "method:\"DELETE\"",
                  "paperOrder", "brokerOrder", "executeTrade", "repair_action"):
        assert token not in text
    assert "Trading authority stays gated" in text
