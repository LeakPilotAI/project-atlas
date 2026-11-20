"""Offline Q7 integration seams; explicit disposable instances only,no activation."""
import asyncio
import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from app.investment.quality_dips_v3 import build_v3_entry_plan
from app.services.paper_epoch_fixture import digest, number


def quality_signal_fixture(inputs, *, quote, observation_id):
    """Use the actual V3 policy,not caller-invented eligibility labels."""
    plan = build_v3_entry_plan(**inputs)
    if inputs["symbol"].upper() != quote["symbol"] or number(str(inputs["current_price"])) != number(quote["price"]):
        raise ValueError("Signal/quote instrument or price mismatch")
    return {"symbol": plan["symbol"], "observation_id": observation_id, "classification": plan["patient_state"],
            "strategy_version": "QUALITY_DIPS_V3", "policy_version": "quality-dips-v3-mos-15-20-25-30-v1",
            "evidence_class": "FORWARD_COLLECTION", "quote": dict(quote),
            "reached_levels": [p["level"] for p in plan["entry_ladder"]["levels"] if p["reached"]],
            "signal_digest": digest({"inputs": inputs, "plan": plan}), "fixture_only": True}


class NativePerpProjectionFixture:
    """Publish canonical overlays to injected actual disposable native stores.

    V1 journal opens remain retained;partial/full current state is additive and
    must never be interpreted as a V1 priced full close or legacy FLAT claim.
    This is not a runtime dispatcher or independent writer-exclusion mechanism.
    """
    def __init__(self, *, journal, journal_path, manual_store):
        self.journal, self.path, self.manual = journal, Path(journal_path), manual_store
        self.expected_observation = digest(self.observe())

    def observe(self):
        raw = self.path.read_bytes() if self.path.exists() else b""
        state = self.manual.load()
        native = self.journal.list_open()
        plans = {p.get("fixture_journal_trade_id"): p for p in state["plans"]}
        if len(plans) != len(state["plans"]) or len(plans) != len(native):
            raise ValueError("Unassociated native fixture inventory;no implicit legacy adoption")
        for row in native:
            plan = plans.get(row["trade_id"])
            if (not plan or not plan.get("canonical_fixture_id")
                    or row.get("features", {}).get("canonical_fixture_id") != plan["canonical_fixture_id"]):
                raise ValueError("Unassociated native fixture position")
        return {"journal_digest": hashlib.sha256(raw).hexdigest(), "manual": state}

    def publish(self, state, receipt):
        if state["strategy"] != "HYPERLIQUID_MANUAL" or digest(self.observe()) != self.expected_observation:
            raise ValueError("Changed native fixture source before publication")
        previous = self.manual.load()
        by_id = {p["canonical_fixture_id"]: p for p in previous["plans"]}
        plans = []
        for ident, p in state["positions"].items():
            plan = by_id.get(ident)
            if plan is None:
                entry, risk, qty = number(p["entry"]), number(p["risk_price"]), number(p["quantity"])
                direction = 1 if p["side"] == "LONG" else -1
                native_id = asyncio.run(self.journal.open_trade(
                    symbol=p["symbol"], side=p["side"], entry=float(entry), stop=float(entry - direction * risk),
                    tp1=float(entry + direction * 2 * risk), tp2=float(entry + direction * 3 * risk),
                    risk_usd=float(risk * qty), fees_bps=2, slippage_bps=2, counts_for_live=False,
                    source="fixture-canonical-manual", features={"canonical_fixture_id": ident, "epoch": state["epoch"]}))
                actual = [r for r in self.journal.list_open() if r["trade_id"] == native_id]
                if (len(actual) != 1 or actual[0].get("features", {}).get("canonical_fixture_id") != ident
                        or actual[0]["symbol"] != p["symbol"] or actual[0]["side"] != p["side"]
                        or actual[0].get("counts_for_live") is not False or actual[0].get("trade_type") != "PAPER"
                        or any(Decimal(str(actual[0][key])) != expected for key, expected in (
                            ("position_size", qty), ("actual_entry_price", entry), ("risk_price", risk),
                            ("fees_bps", Decimal(2)), ("slippage_bps", Decimal(2))))):
                    raise ValueError("Native entry not independently matched to fixture command")
                plan = {"setup_key": ident, "symbol": p["symbol"], "side": p["side"], "status": "ENTERED",
                        "entered_at": datetime.fromtimestamp(state["last_clock"], UTC).isoformat(),
                        "canonical_fixture_id": ident, "fixture_journal_trade_id": native_id}
            plans.append({**plan, "fixture_projection": {**p, "epoch": state["epoch"], "source_revision": state["revision"],
                         "lifecycle": "CLOSED_FIXTURE_ONLY" if number(p["remaining"]) == 0 else "OPEN_FIXTURE_ONLY"}})
        self.manual.save(plans=plans, setup_history=previous["setup_history"])
        self.expected_observation = digest(self.observe())
