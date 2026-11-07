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


def test_research_page_renders_evidence_maturity_contract():
    page=Path("frontend/src/app/research/page.tsx").read_text(encoding="utf-8")
    assert "Research evidence maturity / missing-evidence summary" in page
    assert "DESCRIPTIVE_MATURITY_PRESENCE_MISSING" in page
    assert "Present dimensions" in page
    assert "Missing dimensions" in page
    assert "aggregate_score" in page
    assert "readiness_percentage" in page
    assert "research_evidence_maturity" in page


def test_research_page_renders_maturity_change_history_contract():
    page=Path("frontend/src/app/research/page.tsx").read_text(encoding="utf-8")
    assert "Maturity change history / new-evidence transitions" in page
    assert "DESCRIPTIVE_MATURITY_NEW_EVIDENCE_TRANSITIONS" in page
    assert "MISSING->PRESENT" in page
    assert "PRESENT->PRESENT" in page
    assert "duplicate refresh resistant" in page
    assert "maturity_change_history" in page
    assert "readiness_percentage" in page


def test_research_page_renders_maturity_transition_persistence_contract():
    page=Path("frontend/src/app/research/page.tsx").read_text(encoding="utf-8")
    assert "Maturity transition persistence / reversal" in page
    assert "DESCRIPTIVE_MATURITY_NEXT_NEW_EVIDENCE_CONFIRMATION" in page
    assert "Three qualifying maturity observations are required" in page
    assert "PERSISTED" in page
    assert "REVERSED" in page
    assert "CHANGED AGAIN" in page
    assert "maturity_transition_persistence" in page
    assert "readiness percentage" in page


def test_research_page_renders_maturity_confirmation_sequence_contract():
    page=Path("frontend/src/app/research/page.tsx").read_text(encoding="utf-8")
    assert "Maturity confirmation sequence diagnostics" in page
    assert "DESCRIPTIVE_MATURITY_CONFIRMATION_SEQUENCE" in page
    assert "maturity_confirmation_sequence_diagnostics" in page
    assert "sequence:" in page
    assert "latest" in page
    assert "PERSISTED" in page
    assert "REVERSED" in page
    assert "CHANGED AGAIN" in page


def test_research_page_renders_maturity_sequence_stability_contract():
    page=Path("frontend/src/app/research/page.tsx").read_text(encoding="utf-8")
    assert "Maturity sequence stability / repetition diagnostics" in page
    assert "DESCRIPTIVE_MATURITY_SEQUENCE_STABILITY" in page
    assert "maturity_sequence_stability_diagnostics" in page
    assert "REPEATED OUTCOME" in page
    assert "ALTERNATING PATTERN" in page
    assert "MIXED SEQUENCE" in page
    assert "INSUFFICIENT HISTORY" in page
    assert "repeated latest" in page


def test_research_page_renders_maturity_sequence_run_length_contract():
    page=Path("frontend/src/app/research/page.tsx").read_text(encoding="utf-8")
    assert "Maturity sequence run-length / recent-streak diagnostics" in page
    assert "DESCRIPTIVE_MATURITY_SEQUENCE_RUN_LENGTH" in page
    assert "maturity_sequence_run_length_diagnostics" in page
    assert "current run" in page
    assert "previous run" in page
    assert "run count" in page
    assert "boundary" in page
    assert "runs:" in page


def test_research_page_renders_maturity_sequence_run_boundary_contract():
    page=Path("frontend/src/app/research/page.tsx").read_text(encoding="utf-8")
    assert "Maturity sequence run boundary transition diagnostics" in page
    assert "DESCRIPTIVE_MATURITY_SEQUENCE_RUN_BOUNDARIES" in page
    assert "maturity_sequence_run_boundary_diagnostics" in page
    assert "boundary count" in page
    assert "latest boundary" in page
    assert "boundaries:" in page
    assert "current run" in page


def test_research_page_renders_maturity_sequence_run_boundary_recurrence_contract():
    page=Path("frontend/src/app/research/page.tsx").read_text(encoding="utf-8")
    assert "Maturity sequence run boundary recurrence diagnostics" in page
    assert "DESCRIPTIVE_MATURITY_RUN_BOUNDARY_RECURRENCE" in page
    assert "maturity_sequence_run_boundary_recurrence_diagnostics" in page
    assert "distinct forms" in page
    assert "recurrences:" in page
    assert "latest #" in page
    assert "does not rank frequent transitions" in page
