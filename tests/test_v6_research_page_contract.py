from pathlib import Path


def test_research_page_renders_prospective_consistency_history_contract():
    page=Path("frontend/src/app/research/page.tsx").read_text(encoding="utf-8")
    assert "Prospective multi-window consistency history" in page
    assert "APPEND_ONLY_POINT_IN_TIME_NEW_EVIDENCE_ONLY" in page
    assert "duplicate refreshes do not count" in page
    assert "new prospective evidence required" in page
    assert "Skipped duplicate refreshes" in page
    assert "Cross-window disagreement" in page
    assert '["3","7","14"]' in page
    assert "cannot promote production or unlock capital" in page


def test_research_page_renders_consistency_change_diagnostics_contract():
    page=Path("frontend/src/app/research/page.tsx").read_text(encoding="utf-8")
    assert "Consistency change diagnostics" in page
    assert "DESCRIPTIVE_NEW_EVIDENCE_TRANSITIONS" in page
    assert "Disagreement transition" in page
    assert "comparison changed" in page
    assert "sufficiency changed" in page
    assert "new-evidence-only" in page
    assert "No automatic scoring" in page
