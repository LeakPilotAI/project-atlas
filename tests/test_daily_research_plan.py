from datetime import datetime, timezone
from app.investment.models import PortfolioInput
from app.investment.daily_research_plan import build_plan, persist_daily_plan
from app.investment.prospective_evidence import append_record
from app.investment.adaptive_valuation import version_valuation


def observation():
    return {
        "symbol": "ABC",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_timestamp": datetime.now(timezone.utc).isoformat(),
        "price": 100,
        "observation_id": "one",
        "policy_version": "v3",
        "evidence_class": "FORWARD_COLLECTION",
        "classification": "WATCH",
        "confidence": "UNKNOWN",
        "missing_data": [],
        "features": {},
        "prediction": {"fair_value_anchor": 150, "entry_ladder": {"levels": []}},
        "valuation": {"conservative": 120},
    }


def test_no_invented_capital_and_invalid_config_fails_closed():
    result = build_plan(
        [observation()], PortfolioInput(), {"stage_weights": {"CURRENT": "bad"}}
    )
    assert result["status"] == "BUY_NOTHING_TODAY"
    assert result["current_research_allocation"] == 0
    assert result["available_research_cash"] is None
    assert not result["live_capital_allowed"]


def test_price_alone_never_revises_valuation(tmp_path):
    obs = observation()
    path = tmp_path / "revisions.jsonl"
    first = version_valuation(obs, path)
    before = path.read_bytes()
    second = version_valuation({**obs, "price": 130}, path)
    assert second["revision_status"] == "UNCHANGED"
    assert path.read_bytes() == before
    score_drift = version_valuation(
        {
            **obs,
            "price": 130,
            "features": {"decision_inputs": {"valuation_score": 99}},
            "prediction": {"fair_value_anchor": 190},
        },
        path,
    )
    assert score_drift["revision_status"] == "PRICE_ANCHOR_DRIFT"
    assert path.read_bytes() == before
    assert first["new_values"] == second["new_values"]
    drift = version_valuation(
        {**obs, "price": 130, "prediction": {"fair_value_anchor": 190}}, path
    )
    assert drift["revision_status"] == "PRICE_ANCHOR_DRIFT"
    assert path.read_bytes() == before


def test_daily_plan_keeps_first_snapshot(tmp_path, monkeypatch):
    import app.investment.daily_research_plan as module

    monkeypatch.setattr(module, "version_valuation", lambda _: {})
    observations = tmp_path / "observations.jsonl"
    plans = tmp_path / "plans.jsonl"
    append_record(observations, observation())
    first = persist_daily_plan(
        observations, plans, config={}, portfolio=PortfolioInput()
    )
    before = plans.read_bytes()
    second = persist_daily_plan(
        observations, plans, config={"changed": True}, portfolio=PortfolioInput()
    )
    assert first == second
    assert plans.read_bytes() == before


def test_actionability_requires_existing_evidence_freshness_gate():
    from app.investment.adaptive_valuation import actionability

    obs = observation()
    obs["features"] = {
        "decision_inputs": {"thesis_intact": True},
        "evidence_gate": {"gate_passed": False, "blockers": ["stale research"]},
    }
    result = actionability(obs, {"minimum_conservative_upside": 0.1})
    assert result["status"] == "WAIT"
    assert "stale research" in result["blockers"]


def test_intraday_valuation_changes_append_without_performance_observations(tmp_path):
    from app.investment.adaptive_valuation import review_current_valuations
    from app.investment.prospective_evidence import read_records

    path = tmp_path / "valuations.jsonl"
    source = {
        "symbol": "ABC",
        "price": 100,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    features = {
        "normalization_value": {"conservative": 120, "base": 150, "optimistic": 180},
        "quality_dips_v3": {"fair_value_anchor": 150, "entry_ladder": {"levels": []}},
    }
    board = [{"symbol": "ABC", "quality_dips_v2": features}]
    review_current_valuations(board, [source], path)
    first = path.read_bytes()
    review_current_valuations(board, [{**source, "price": 110}], path)
    assert path.read_bytes() == first
    features["normalization_value"]["base"] = 160
    features["quality_dips_v3"]["fair_value_anchor"] = 160
    review_current_valuations(board, [source], path)
    rows = read_records(path)
    assert len(rows) == 2
    assert rows[1]["old_values"]["fair_value_anchor"] == 150
    assert rows[1]["new_values"]["fair_value_anchor"] == 160
    assert rows[1]["observation_id"] is None
    assert path.read_bytes().startswith(first)


def test_research_allocation_respects_cash_reserve_and_shared_sector_cap():
    from app.investment.enums import RiskTolerance, InvestmentHorizon

    portfolio = PortfolioInput(
        portfolio_value=10000,
        available_cash=1000,
        minimum_cash_reserve=500,
        maximum_position_percent=10,
        maximum_sector_exposure_percent=2,
        risk_tolerance=RiskTolerance.MODERATE,
        investment_horizon=InvestmentHorizon.YEARS,
        provided=True,
    )
    obs = observation()
    obs["source_snapshot"] = {"sector": "Technology"}
    obs["features"] = {
        "decision_inputs": {"thesis_intact": True},
        "evidence_gate": {"gate_passed": True},
    }
    plan = build_plan(
        [obs, {**obs, "symbol": "DEF", "observation_id": "two"}],
        portfolio,
        {
            "target_allocations": {"QUALITY_DIPS": 1},
            "stage_weights": {"CURRENT": 0.5, "L1": 0.5},
            "minimum_conservative_upside": 0.1,
        },
    )
    total = sum(
        sum(row["staged_research_capital"].values()) for row in plan["quality_dips"]
    )
    assert total == 200  # Shared 2% sector cap, not 200 for each candidate.
    assert plan["current_research_allocation"] == 100
    assert plan["reserve_cash"] >= portfolio.minimum_cash_reserve
