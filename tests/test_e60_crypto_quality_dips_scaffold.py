from app.investment.quality_dips_research_envelope import (
    CRYPTO_EVIDENCE_DIMENSIONS, build_crypto_research_envelope,
)
from app.investment.quality_dips_v3 import build_v3_entry_plan
from app.investment.quality_dips_v3_state import QualityDipsV3StateStore

def evidence():
    return {key: {"status":"UNKNOWN","source":"inactive-e60"} for key in CRYPTO_EVIDENCE_DIMENSIONS}

def test_crypto_envelope_is_inert_and_zero_authority():
    row=build_crypto_research_envelope(
        symbol="btc", allowlisted=True, liquidity_qualified=True,
        evidence=evidence(), provenance=["e60-design"], freshness={"as_of":"unknown"},
        risk_flags=["RESEARCH_ONLY"],
    )
    assert row.asset_class=="CRYPTO" and row.symbol=="BTC" and row.universe_eligible is True
    assert row.active is False and row.can_emit_signal is False and row.can_schedule is False
    for name in ("paper_entry_authority","execution_authority","strategy_selection_authority",
                 "threshold_mutation_authority","promotion_authority","live_capital_allowed"):
        assert getattr(row,name) is False

def test_crypto_universe_requires_allowlist_and_liquidity():
    assert build_crypto_research_envelope(symbol="BTC",allowlisted=False,liquidity_qualified=True,evidence=evidence()).universe_eligible is False
    assert build_crypto_research_envelope(symbol="BTC",allowlisted=True,liquidity_qualified=False,evidence=evidence()).universe_eligible is False

def test_missing_crypto_evidence_fails_closed_as_risk_flags():
    row=build_crypto_research_envelope(symbol="ETH",allowlisted=True,liquidity_qualified=True,evidence={})
    assert len([x for x in row.risk_flags if x.startswith("MISSING:")])==len(CRYPTO_EVIDENCE_DIMENSIONS)

def test_crypto_scaffold_does_not_touch_stock_v3_state_or_policy(tmp_path):
    store=QualityDipsV3StateStore(tmp_path/"stock.json")
    before=(dict(store.snapshots),dict(store.events))
    build_crypto_research_envelope(symbol="SOL",allowlisted=True,liquidity_qualified=True,evidence=evidence())
    assert (store.snapshots,store.events)==before
    plan=build_v3_entry_plan(
        symbol="MSFT",current_price=80,
        normalization={"conservative":100,"base":110,"optimistic":120},
        quality_score=90,fundamentals_score=85,valuation_score=80,
        drawdown_percentile=90,evidence_quality="HIGH",thesis_intact=True,value_trap=False,
    )
    assert plan["cycle"]=="QUALITY_DIPS_V3_MARGIN_OF_SAFETY"
    assert plan["execution"]=="MANUAL_ONLY" and plan["live_capital_allowed"] is False
