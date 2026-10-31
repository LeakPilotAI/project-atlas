"""Selected-account V1 policy, offline evidence only; never operational authority.

Inception pins explicitly supplied instrument/execution facts and ranking receipt
digests. These pins must come from separately accepted evidence in any future
runtime integration. Locally constructing this contract authenticates nothing.
"""
from decimal import Decimal, localcontext


def verify_reached_level(ladder, level, price):
    """Use the existing frozen ladder; never infer execution from old rank alone."""
    from app.services.paper_financial_replay import number

    if type(ladder) is not dict or ladder.get("ready") is not True or type(ladder.get("levels")) is not list:
        raise ValueError("LADDER_EVIDENCE_INVALID")
    levels = ladder["levels"]
    if (any(type(item) is not dict or item.get("level") not in ("L1", "L2", "L3", "L4")
            or type(item.get("reached")) is not bool for item in levels)
            or len({item["level"] for item in levels}) != len(levels)):
        raise ValueError("LADDER_EVIDENCE_INVALID")
    selected = [item for item in levels if item["level"] == level and item["reached"]]
    if len(selected) != 1 or type(selected[0].get("limit_price")) not in (str, int, float):
        raise ValueError("LADDER_LEVEL_UNAVAILABLE")
    limit = number(str(selected[0]["limit_price"]))
    if limit <= 0 or number(price) > limit:
        raise ValueError("CURRENT_PRICE_ABOVE_LEVEL")


def validate_policy(manifest):
    from app.services.paper_financial_replay import text

    p = manifest["account_policy"]
    dynamic = manifest["schema"] == "PAPER_EPOCH_SELECTED_QD_V3"
    fields = {"schema", "evidence_scope", "instruments", "ranking_max_age_seconds",
              "max_entry_usd", "max_positions"}
    fields |= {"account_id", "ranking_authority"} if dynamic else {"ranking_receipts"}
    schema = "QD_SELECTED_ACCOUNT_POLICY_V2" if dynamic else "QD_SELECTED_ACCOUNT_POLICY_V1"
    if (type(p) is not dict or set(p) != fields or p["schema"] != schema
            or p["evidence_scope"] != "DISPOSABLE_ONLY" or manifest["strategy"] != "QUALITY_DIPS"
            or manifest["opening_cash"] != "1000" or manifest["initial_net_r"] != "0"
            or (manifest["fees_bps"], manifest["slippage_bps"]) != ("2", "2")
            or p["max_entry_usd"] != "100" or type(p["max_positions"]) is not int or p["max_positions"] != 1
            or type(p["ranking_max_age_seconds"]) is not int or not 1 <= p["ranking_max_age_seconds"] <= 600):
        raise ValueError("POLICY_INVALID")
    instruments = p["instruments"]
    if dynamic:
        text(p["account_id"])
        text(p["ranking_authority"])
    if type(instruments) is not dict or not 1 <= len(instruments) <= 4096:
        raise ValueError("EVIDENCE_PINS_INVALID")
    if not dynamic:
        pins = p["ranking_receipts"]
        if (type(pins) is not list or not 1 <= len(pins) <= 4096
                or any(type(pin) is not str or len(pin) != 64 or any(c not in "0123456789abcdef" for c in pin) for pin in pins)
                or len(set(pins)) != len(pins)):
            raise ValueError("EVIDENCE_PINS_INVALID")
    identities = set()
    for symbol, instrument in instruments.items():
        text(symbol)
        if (type(instrument) is not dict or set(instrument) != {"instrument_id", "asset_class", "fractional", "quote_source"}
                or instrument["asset_class"] not in ("STOCK", "ETF") or type(instrument["fractional"]) is not bool):
            raise ValueError("INSTRUMENT_UNSUPPORTED")
        ident = text(instrument["instrument_id"])
        text(instrument["quote_source"])
        if ident in identities:
            raise ValueError("INSTRUMENT_ID_DUPLICATE")
        identities.add(ident)


def validate_command(manifest, state, command):
    """Return audit reason codes; rank is selection evidence, never consent."""
    from app.services.paper_financial_replay import body, digest, number, strict, text

    p = manifest["account_policy"]
    dynamic = manifest["schema"] == "PAPER_EPOCH_SELECTED_QD_V3"
    schema = "PAPER_COMMAND_SELECTED_QD_V3" if dynamic else "PAPER_COMMAND_SELECTED_QD_V2"
    if command.get("schema") != schema or command.get("manual") is not True:
        raise ValueError("MANUAL_CONFIRMATION_REQUIRED")
    evidence = command.get("eligibility")
    if type(evidence) is not dict:
        raise ValueError("ELIGIBILITY_MISSING")
    if command.get("kind") == "ENTRY":
        symbol = command.get("symbol")
    else:
        position = state["positions"].get(command.get("position_id"))
        if position is None:
            raise ValueError("POSITION_UNKNOWN")
        symbol = position["symbol"]
    instrument = p["instruments"].get(symbol)
    if instrument is None or evidence.get("instrument_id") != instrument["instrument_id"]:
        raise ValueError("INSTRUMENT_IDENTITY_UNVERIFIED")
    q = command.get("quote")
    if type(q) is not dict or q.get("source_id") != instrument["quote_source"] or q.get("symbol") != symbol:
        raise ValueError("PRICE_SOURCE_MISMATCH")
    qty = number(command["quantity"])
    if dynamic:
        decision = command.get("authority_evidence")
        if type(decision) is not dict or set(decision) != {"candidate", "execution", "approval", "context"}:
            raise ValueError("DECISION_EVIDENCE_MISSING")
        context = decision["context"]
        execution = decision["execution"]
        expected = {"account_id": p["account_id"], "epoch": manifest["epoch"], "operation_id": command["operation_id"],
                    "policy_digest": digest(p), "instrument_id": instrument["instrument_id"], "kind": command["kind"],
                    "quantity": command["quantity"], "source_revision": command["expected_source_revision"],
                    "position_id": command.get("position_id"), "position_revision": command.get("expected_position_revision"),
                    "quote_digest": digest(q), "candidate_digest": digest(decision["candidate"]),
                    "execution_digest": digest(execution),
                    "timestamp": command["timestamp"]}
        approval = decision["approval"]
        if (body(context) != body(expected) or type(approval) is not dict or approval.get("approved") is not True
                or approval.get("binding") != digest(expected) or not approval.get("receipt_id")
                or execution.get("instrument", {}).get("instrument_id") != instrument["instrument_id"]
                or body(execution.get("quote")) != body(q)
                or execution["execution_proof"].get("binding") != digest({"instrument": execution["instrument"], "quote": execution["source_quote"]})):
            raise ValueError("DECISION_BINDING_MISMATCH")
        if command["kind"] == "ENTRY":
            candidate = strict(decision["candidate"])
            if (candidate.get("schema") != "QD_CANDIDATE_EVIDENCE_V1"
                    or body(candidate.get("ranking")) != body(evidence.get("ranking"))
                    or body(candidate.get("execution")) != body(execution)
                    or candidate["ranking"]["source_id"] != p["ranking_authority"]
                    or type(candidate.get("expires_at")) is not int or command["timestamp"] >= candidate["expires_at"]):
                raise ValueError("CANDIDATE_BINDING_MISMATCH")
            verify_reached_level(candidate["source_bundle"]["observation"]["prediction"]["entry_ladder"],
                                 candidate["ranking"]["level"], q["price"])
        elif decision["candidate"] is not None:
            raise ValueError("EXIT_MUST_NOT_REQUIRE_RANK")
    if not instrument["fractional"] and qty != qty.to_integral_value():
        raise ValueError("FRACTIONAL_EXECUTION_UNSUPPORTED")
    if command.get("kind") == "EXIT":
        if set(evidence) != {"instrument_id"}:
            raise ValueError("EXIT_EVIDENCE_INVALID")
        return ["PINNED_EXECUTION_IDENTITY", "MANUAL_EXIT", "RANK_NOT_REQUIRED_FOR_HELD_POSITION"]
    if set(evidence) != {"instrument_id", "ranking"}:
        raise ValueError("ENTRY_EVIDENCE_INVALID")
    rank = evidence["ranking"]
    fields = {"symbol", "instrument_id", "observation_id", "level", "rank", "ranked_at", "source_id", "revision",
              "strategy_version", "policy_version", "evidence_class", "classification", "reached_levels"}
    if (type(rank) is not dict or set(rank) != fields or (not dynamic and digest(rank) not in p["ranking_receipts"])
            or rank["symbol"] != symbol or rank["instrument_id"] != instrument["instrument_id"]
            or rank["strategy_version"] != "QUALITY_DIPS_V3"
            or rank["policy_version"] != "quality-dips-v3-mos-15-20-25-30-v1"
            or rank["evidence_class"] != "FORWARD_COLLECTION"
            or rank["classification"] not in ("ACCUMULATION", "DEEP_VALUE", "GENERATIONAL")
            or rank["level"] not in ("L1", "L2", "L3", "L4")
            or type(rank["reached_levels"]) is not list or rank["level"] not in rank["reached_levels"]
            or type(rank["rank"]) is not int or rank["rank"] < 1
            or type(rank["revision"]) is not int or rank["revision"] < 1
            or type(rank["ranked_at"]) is not int or type(command.get("timestamp")) is not int
            or not 0 <= command["timestamp"] - rank["ranked_at"] <= p["ranking_max_age_seconds"]):
        raise ValueError("RANKING_UNVERIFIED_OR_STALE")
    text(rank["observation_id"])
    text(rank["source_id"])
    if command.get("origin_ref") != rank["observation_id"] + ":" + rank["level"]:
        raise ValueError("SIGNAL_IDENTITY_MISMATCH")
    if any(number(position["remaining"]) > 0 for position in state["positions"].values()):
        raise ValueError("ONE_POSITION_NO_SCALE_IN")
    # Compare exact products, not a rounded 28-digit value at the $100 boundary.
    price = number(q["price"])
    if max(len(x.as_tuple().digits) for x in (price, qty)) > 128 or max(abs(x.adjusted()) for x in (price, qty)) > 128:
        raise ValueError("DECIMAL_CAPACITY_EXCEEDED")
    with localcontext() as context:
        context.prec = 512
        notional = price * qty
        if notional > Decimal(p["max_entry_usd"]):
            raise ValueError("ENTRY_NOTIONAL_LIMIT")
        if notional > number(state["cash"]):
            raise ValueError("INSUFFICIENT_CASH")
    rank_reason = "CURRENT_GENERATION_BOUND" if dynamic else "PINNED_RANKING"
    return [rank_reason, "PINNED_EXECUTION_IDENTITY", "MANUAL_ENTRY", "ENTRY_LIMITS_VERIFIED"]
