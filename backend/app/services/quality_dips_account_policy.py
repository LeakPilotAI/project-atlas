"""Selected-account V1 policy, offline evidence only; never operational authority.

Inception pins explicitly supplied instrument/execution facts and ranking receipt
digests. These pins must come from separately accepted evidence in any future
runtime integration. Locally constructing this contract authenticates nothing.
"""
from decimal import Decimal, localcontext


def validate_policy(manifest):
    from app.services.paper_financial_replay import text

    p = manifest["account_policy"]
    fields = {"schema", "evidence_scope", "instruments", "ranking_receipts", "ranking_max_age_seconds",
              "max_entry_usd", "max_positions"}
    if (type(p) is not dict or set(p) != fields or p["schema"] != "QD_SELECTED_ACCOUNT_POLICY_V1"
            or p["evidence_scope"] != "DISPOSABLE_ONLY" or manifest["strategy"] != "QUALITY_DIPS"
            or manifest["opening_cash"] != "1000" or manifest["initial_net_r"] != "0"
            or (manifest["fees_bps"], manifest["slippage_bps"]) != ("2", "2")
            or p["max_entry_usd"] != "100" or type(p["max_positions"]) is not int or p["max_positions"] != 1
            or type(p["ranking_max_age_seconds"]) is not int or not 1 <= p["ranking_max_age_seconds"] <= 600):
        raise ValueError("POLICY_INVALID")
    instruments, pins = p["instruments"], p["ranking_receipts"]
    if (type(instruments) is not dict or not 1 <= len(instruments) <= 4096
            or type(pins) is not list or not 1 <= len(pins) <= 4096
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
    from app.services.paper_financial_replay import digest, number, text

    p = manifest["account_policy"]
    if command.get("schema") != "PAPER_COMMAND_SELECTED_QD_V2" or command.get("manual") is not True:
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
    if (type(rank) is not dict or set(rank) != fields or digest(rank) not in p["ranking_receipts"]
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
    return ["PINNED_RANKING", "PINNED_EXECUTION_IDENTITY", "MANUAL_ENTRY", "ENTRY_LIMITS_VERIFIED"]
