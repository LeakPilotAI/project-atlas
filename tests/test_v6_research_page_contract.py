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


def test_research_page_renders_transition_persistence_contract():
    page=Path("frontend/src/app/research/page.tsx").read_text(encoding="utf-8")
    assert "Transition persistence / reversal" in page
    assert "DESCRIPTIVE_NEXT_NEW_EVIDENCE_CONFIRMATION" in page
    assert "minimum 3 qualifying observations" in page
    assert "Disagreement outcome" in page
    assert "BECAME INSUFFICIENT" in page
    assert "confirmation checks" in page
    assert "no production score" in page.lower()


def test_research_page_renders_confirmation_sequence_contract():
    page=Path("frontend/src/app/research/page.tsx").read_text(encoding="utf-8")
    assert "Confirmation sequence diagnostics" in page
    assert "DESCRIPTIVE_CONFIRMATION_SEQUENCE" in page
    assert "Disagreement sequence" in page
    assert "sequence:" in page
    assert "automatic_scoring" in page
    assert "best_window_selection" in page
    assert "production_promoted" in page


def test_research_page_renders_evidence_sufficiency_gap_contract():
    page=Path("frontend/src/app/research/page.tsx").read_text(encoding="utf-8")
    assert "Evidence sufficiency gaps" in page
    assert "DESCRIPTIVE_EVIDENCE_GAPS" in page
    assert "Membership gap" in page
    assert "Confirmation observation gap" in page
    assert "readiness_score" in page
    assert "evidence_sufficiency_gaps" in page
