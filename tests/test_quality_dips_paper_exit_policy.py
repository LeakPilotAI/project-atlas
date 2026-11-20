from app.investment.quality_dips_paper_exit_policy import evaluate_exit

def test_nonterminal_observation_stays_open():
    result = evaluate_exit({"classification": "ACCUMULATION", "prediction": {"blockers": []}})
    assert result["terminal"] is False
    assert result["price_only_exit_allowed"] is False

def test_thesis_state_is_terminal():
    result = evaluate_exit({"classification": "THESIS_BROKEN", "prediction": {"blockers": []}})
    assert result["terminal"] is True
    assert result["terminal_reason"] == "THESIS_BROKEN"

def test_ordinary_watch_blocker_stays_open():
    result = evaluate_exit({"classification": "WATCH", "prediction": {"blockers": ["evidence below MEDIUM"]}})
    assert result["terminal"] is False
