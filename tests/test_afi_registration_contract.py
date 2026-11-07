import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def register():
    return json.loads((ROOT/"docs/AFI_MILESTONE_REGISTER.json").read_text())


def test_all_ten_official_milestones_are_in_permanent_master():
    data=register();raw=(ROOT/"PROJECT_ATLAS_MASTER_ROADMAP.txt").read_text(encoding="utf-8")
    start=raw.index("=== ATLAS FORECAST INTELLIGENCE (AFI) - PERMANENT INITIATIVE V1 ===")
    end=raw.index("=== END ATLAS FORECAST INTELLIGENCE (AFI) V1 ===")
    assert start < end < raw.index("=== ATLAS MANAGED CURRENT CHECKPOINT V1 ===")
    assert [m["id"] for m in data["milestones"]]==[f"AFI-{i}" for i in range(1,11)]
    for milestone in data["milestones"]:
        line=f"{milestone['id']} - {milestone['name']}: {milestone['status']}"
        assert raw[start:end].count(line)==1
        assert milestone["minimum_acceptance"]


def test_market_priority_horizons_and_scenario_refusal_are_explicit():
    data=register()
    assert data["market_priority"]==["US_EQUITIES","ETFS","CRYPTOCURRENCIES"]
    assert len(data["horizons"])==11
    for horizon in ("1_DAY","5_DAYS","1_WEEK","SCENARIO_2030","SCENARIO_2040","SCENARIO_2050"):
        assert horizon in data["horizons"]
    raw=(ROOT/"docs/AFI_INITIATIVE_AND_EVIDENCE_CONTRACTS.md").read_text(encoding="utf-8")
    assert "never precise or guaranteed" in raw
    assert "not independently" in raw or "not authenticated" in raw


def test_existing_phases_and_continuity_link_afi_without_granting_authority():
    raw=(ROOT/"PROJECT_ATLAS_MASTER_ROADMAP.txt").read_text(encoding="utf-8")
    for header in ("PHASE 2 - ATLAS RESEARCH EVIDENCE ENGINE","PHASE 4 - CROSS-MARKET INTELLIGENCE"):
        assert "AFI dependency" in raw[raw.index(header):raw.index(header)+300]
    assert register()["production_release"]=="NO-GO"
    assert register()["automated_trading_authority"] is False
    continuity=(ROOT/"docs/CONTINUOUS_RUNTIME_ISOLATED_DEVELOPMENT_READINESS_2026-10-19.md").read_text(encoding="utf-8")
    assert "AFI continuity addendum" in continuity
    assert "AFI_MILESTONE_REGISTER.json" in continuity


def test_production_lock_and_21_gate_authority_remain_denied():
    from app.core.production_startup_lock import (
        ProductionStartupRefused,
        require_startup_authorization,
    )
    with pytest.raises(ProductionStartupRefused): require_startup_authorization()
    matrix=json.loads((ROOT/"docs/R7E47O_PHASE1_RELEASE_GATE_MATRIX.json").read_text())
    assert len(matrix["gates"])==21 and matrix["production_release"]=="NO-GO"
