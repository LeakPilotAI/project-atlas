"""Synthetic tier schedules; no operational margin or leverage approval."""
from decimal import Decimal

import pytest
from app.services.paper_epoch_fixture import create_epoch_fixture
from app.services.paper_perp_transition import tier_requirement
from test_perp_financial_v2 import action, audit, entry, manifest


def tier_policy():
    return {"schema": "PAPER_PERP_MARGIN_POLICY_V1", "source_cut": "synthetic-meta", "table_id": "synthetic-tiers",
            "tiers": [{"lower_bound": "0", "max_leverage": 20}, {"lower_bound": "40", "max_leverage": 10}],
            "maintenance_quantum": "0.000001", "rounding": "CEILING"}


@pytest.mark.parametrize("notional,expected", [("0", "0"), ("39", ".975"), ("40", "1"), ("41", "1.05"), ("50", "1.5")])
def test_continuous_piecewise_tiers(notional, expected):
    assert tier_requirement(tier_policy(), Decimal(notional), "synthetic-meta")[0] == Decimal(expected)


@pytest.mark.parametrize("damage", ["source", "rounding", "duplicate", "increasing-leverage", "missing-zero", "precision"])
def test_tier_substitution_or_understated_rounding_refuses(damage):
    p = tier_policy()
    if damage == "source": p["source_cut"] = "foreign"
    elif damage == "rounding": p["rounding"] = "FLOOR"
    elif damage == "duplicate": p["tiers"][1]["lower_bound"] = "0"
    elif damage == "increasing-leverage": p["tiers"][1]["max_leverage"] = 40
    elif damage == "missing-zero": p["tiers"][0]["lower_bound"] = "1"
    else: p["maintenance_quantum"] = "1"
    with pytest.raises(ValueError): tier_requirement(p, Decimal(50), "synthetic-meta")


def test_tier_entry_and_mark_are_independently_audited(tmp_path):
    st = create_epoch_fixture(tmp_path / "perp.db", manifest())
    c = entry()
    c["schema"] = "PAPER_PERP_MARGIN_ENTRY_V1"
    c["evidence"]["margin_policy"] = tier_policy()
    st.execute(c)
    assert Decimal(st.snapshot()["maintenance_margin"]) == Decimal("1.5")
    st.execute(action(st, "MARK", "mark-tier", 3603, evidence={"source": "synthetic-book", "instrument_cut": "synthetic-meta",
                      "symbol": "BTC", "observed_at": 3603, "mark": "120", "source_id": "synthetic-mark"}))
    assert Decimal(st.snapshot()["maintenance_margin"]) == 2
    audit(st)


def test_nonterminating_tier_rate_rounds_requirement_up_not_cash(tmp_path):
    st = create_epoch_fixture(tmp_path / "perp.db", manifest())
    c = entry()
    c["schema"] = "PAPER_PERP_MARGIN_ENTRY_V1"
    p = tier_policy()
    p["tiers"] = [{"lower_bound": "0", "max_leverage": 3}]
    c["evidence"]["margin_policy"] = p
    st.execute(c)
    assert st.snapshot()["maintenance_margin"] == "8.333334"
    assert Decimal(st.snapshot()["cash"]) == Decimal("999.98")
    audit(st)
