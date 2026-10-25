"""Unregistered router factory. No default readers, dispatcher or startup hooks.

Read dependencies must be independently accepted read-only capabilities. Python
cannot sandbox a malicious injected callable; no such callable is trusted here
merely because it implements this protocol. GET never receives a writer object.
"""
import re
from decimal import DecimalException

from fastapi import APIRouter, HTTPException

from app.investment.quality_dips_read_capability import CurrentReadEvidenceUnverified
from app.services.paper_financial_replay import body, digest, number, strict


def financial_view(*, reader, verifier, clock, account_id, epoch):
    unavailable = {"schema": "QD_SELECTED_FINANCIAL_VIEW_V1", "account_id": account_id, "epoch": epoch,
                   "status": "UNAVAILABLE", "cash": None, "realized": None, "positions": None,
                   "valuation": None, "report_status": "UNAVAILABLE", "reasons": ["PROJECTION_UNAVAILABLE"],
                   "startup_authorized": False}
    try:
        now = clock()
        payload = strict(body(reader.read_committed(account_id, epoch)))
        proof = verifier.verify(payload, account_id=account_id, epoch=epoch, now=now)
        if (type(proof) is not dict or proof.get("verified") is not True or proof.get("binding") != digest(payload)
                or payload.get("account_id") != account_id or payload.get("epoch") != epoch
                or payload.get("schema") != "QD_COMMITTED_PROJECTION_V1"
                or payload.get("status") != "ACKNOWLEDGED" or type(now) is not int
                or type(payload.get("observed_at")) is not int or not 0 <= now - payload["observed_at"] <= 30
                or type(payload.get("source_revision")) is not int or payload["source_revision"] < 0
                or not payload.get("source_identity") or not payload.get("policy_digest")):
            return {**unavailable, "status": "UNKNOWN", "reasons": ["PROJECTION_UNVERIFIED_OR_STALE"]}
        state = payload["state"]
        inception = payload.get("inception")
        projection_revision = payload.get("projection_revision")
        if inception is not None and (type(inception) is not dict
                or inception.get("schema") != "QD_SELECTED_INCEPTION_VIEW_V1"
                or inception.get("account_id") != account_id or inception.get("epoch") != epoch
                or inception.get("policy_digest") != payload["policy_digest"] or inception.get("currency") != "USD"
                or type(inception.get("policy_schema")) is not str or not inception["policy_schema"]
                or type(inception.get("opening_cash")) is not str
                or number(inception.get("opening_cash")) <= 0):
            return {**unavailable, "status": "UNKNOWN", "reasons": ["INCEPTION_SCOPE_UNVERIFIED"]}
        if projection_revision is not None and (type(projection_revision) is not int
                or projection_revision != payload["source_revision"]):
            return {**unavailable, "status": "UNKNOWN", "reasons": ["PROJECTION_REVISION_MISMATCH"]}
        if (type(state["revision"]) is not int or state["revision"] != payload["source_revision"]
                or number(state["cash"]) < 0 or number(state["costs"]) < 0
                or number(state["gross"]) - number(state["costs"]) != number(state["net"])
                or payload.get("report_status", "UNAVAILABLE") not in ("UNAVAILABLE", "UNKNOWN", "INCOMPLETE", "COMPLETE")
                or type(state["positions"]) is not dict
                or any(type(position) is not dict or not 0 <= number(position["remaining"]) <= number(position["quantity"])
                       for position in state["positions"].values())):
            return {**unavailable, "status": "UNKNOWN", "reasons": ["PROJECTION_ACCOUNTING_INVALID"]}
        autonomous = payload.get("autonomous")
        breakdown = payload.get("cost_breakdown")
        if autonomous is not None:
            from app.services.quality_dips_autonomous_integration import validate_activity
            validate_activity(autonomous, now=now)
            if (type(breakdown) is not dict or set(breakdown) != {"fees", "slippage", "basis"}
                    or breakdown["basis"] != "REALIZED_COSTS_EQUAL_2BPS_PER_SIDE"
                    or number(breakdown["fees"]) < 0 or number(breakdown["slippage"]) < 0
                    or number(breakdown["fees"]) + number(breakdown["slippage"]) != number(state["costs"])):
                raise ValueError("AUTO_COST_BREAKDOWN_INVALID")
        cash_costs = payload.get("cash_cost_evidence")
        if autonomous is not None and (type(cash_costs) is not dict
                or set(cash_costs) != {"schema", "fees", "slippage", "unallocated_entry_costs"}
                or cash_costs["schema"] != "QD_AUTO_CASH_COSTS_V1"
                or any(number(cash_costs[k]) < 0 for k in ("fees", "slippage", "unallocated_entry_costs"))
                or number(cash_costs["fees"]) + number(cash_costs["slippage"]) != number(state["costs"]) + number(cash_costs["unallocated_entry_costs"])):
            raise ValueError("AUTO_CASH_COSTS_INVALID")
        return {"schema": "QD_SELECTED_FINANCIAL_VIEW_V1", "account_id": account_id, "epoch": epoch,
                **({"autonomous": autonomous, "available_cash": state["cash"], "cash_cost_evidence": cash_costs} if autonomous is not None else {}),
                "status": "ACKNOWLEDGED", "cash": state["cash"],
                "realized": {**{key: state[key] for key in ("gross", "costs", "net")},
                             "fees": breakdown["fees"] if breakdown else None, "slippage": breakdown["slippage"] if breakdown else None},
                "positions": {key: value for key, value in state["positions"].items() if number(value["remaining"]) > 0},
                "source_revision": state["revision"], "source_identity": payload["source_identity"],
                "policy_digest": payload["policy_digest"], "observed_at": payload["observed_at"],
                "inception": inception, "projection_revision": projection_revision,
                "valuation": None, "report_status": payload.get("report_status", "UNAVAILABLE"),
                "report": payload.get("report"), "selection": payload.get("selection"),
                "unavailable_metrics": ["TOTAL_EQUITY", "UNREALIZED_PNL", "FEES_BREAKDOWN", "SLIPPAGE_BREAKDOWN"],
                "lifecycle_status": "NOT_EVALUATED", "startup_authorized": False}
    except CurrentReadEvidenceUnverified:
        return {**unavailable, "status": "UNKNOWN", "reasons": ["CURRENT_PIN_UNVERIFIED"]}
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, AttributeError, DecimalException):
        return unavailable


def create_router(*, reader, verifier, clock, account_id, epoch, commands=None, market_reader=None, unified_reader=None):
    router = APIRouter(prefix="/api/investments/quality-dips/selected-paper", tags=["selected-paper-unregistered"])

    @router.get("")
    def get_selected_paper():
        result = financial_view(reader=reader, verifier=verifier, clock=clock, account_id=account_id, epoch=epoch)
        if market_reader is not None:
            from app.investment.alpaca_iex import IEXFeed
            if type(market_reader) is not IEXFeed:
                raise HTTPException(status_code=503, detail='IEX_CACHE_READER_REQUIRED')
            result['market_data'] = market_reader.snapshot()
        if unified_reader is not None:
            from app.services.unified_paper_runtime import UnifiedMarketReadCapability
            if type(unified_reader) is not UnifiedMarketReadCapability:
                raise HTTPException(status_code=503, detail='UNIFIED_READ_CAPABILITY_REQUIRED')
            try:
                result['multi_market'] = unified_reader.read()
            except (ValueError, OSError):
                result['multi_market'] = None  # Never substitute unverified balances or startup status.
        return result

    @router.post("/commands")
    def command_selected_paper(request: dict):
        if commands is None:
            raise HTTPException(status_code=403, detail="COMMAND_DISPATCH_NOT_ENROLLED")
        try:
            return commands.execute(request)
        except (ValueError, KeyError, TypeError, DecimalException) as exc:
            reason = str(exc)
            reason = reason if re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", reason) else "EVIDENCE_UNAVAILABLE"
            raise HTTPException(status_code=409, detail={"code": "COMMAND_REFUSED", "reason": reason}) from exc

    return router
