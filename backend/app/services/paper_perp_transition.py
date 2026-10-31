"""V2 perpetual arithmetic inside FS1, not a ledger or source authenticator.

This schema is disposable-only. Evidence identities are pinned simulation inputs;
they confer neither provider authenticity nor operational trading authority.
Quotes are unadjusted book prices. Slippage is a separate cash charge, once.
Funding uses explicit hourly oracle settlement, never an assumed zero rate.
Margin is an initial risk reservation, not exchange withdrawable margin. Fees
are cash-paid; settled funding is allocated to remaining-position mark risk.
Cross-margin and automatic margin top-ups are unsupported. Explicitly versioned
margin policies add pinned tier calculations without changing legacy V2 records.
"""
import copy
from decimal import Decimal, Inexact, localcontext
from fractions import Fraction
from zoneinfo import ZoneInfo

from app.services.paper_financial_replay import digest, number, text

SCHEMA = "PAPER_EPOCH_PERP_FIXTURE_V2"


def tier_requirement(policy, notional, source_cut):
    """Conservative USDC requirement from an explicitly pinned tier schedule."""
    exact(policy, "schema source_cut table_id tiers maintenance_quantum rounding")
    if (policy["schema"] != "PAPER_PERP_MARGIN_POLICY_V1" or policy["source_cut"] != source_cut
            or policy["rounding"] != "CEILING" or type(policy["tiers"]) is not list or not 1 <= len(policy["tiers"]) <= 16):
        raise ValueError("Pinned bounded margin policy required")
    text(policy["table_id"])
    quantum = number(policy["maintenance_quantum"])
    if quantum not in tuple(Decimal(10) ** -n for n in range(6, 13)):
        raise ValueError("Explicit conservative maintenance precision required")
    prior, leverage, amount, selected = None, None, Fraction(0), None
    for i, row in enumerate(policy["tiers"]):
        exact(row, "lower_bound max_leverage")
        lower, lev = number(row["lower_bound"]), integer(row["max_leverage"])
        if lev < 1 or lev > 100 or lower < 0 or (i == 0 and lower != 0) or (prior is not None and (lower <= prior or lev > leverage)):
            raise ValueError("Ordered continuous margin tiers required")
        if prior is not None:
            width = max(number("0"), min(notional, lower) - prior)
            amount += Fraction(width) / (2 * leverage)
        if notional >= lower: selected = lev
        prior, leverage = lower, lev
    amount += Fraction(max(number("0"), notional - prior)) / (2 * leverage)
    units = amount / Fraction(quantum)
    rounded = (units.numerator + units.denominator - 1) // units.denominator
    return quantum * rounded, selected


def maintenance(p, policy):
    notional = number(p["mark"]) * number(p["remaining"])
    if "margin_policy" in p:
        return tier_requirement(p["margin_policy"], notional, policy["instrument_cut"])[0]
    return notional * number(policy["maintenance_rate"])


def exact(value, fields):
    if type(value) is not dict or set(value) != set(fields.split()):
        raise ValueError("Exact perpetual evidence schema required")


def integer(value):
    if type(value) is not int or value < 0:
        raise ValueError("Nonnegative integer evidence required")
    return value


def validate_manifest(m):
    exact(m, "schema epoch strategy currency opening_cash opened_at timezone release provenance initial_net_r cost_policy perp_policy")
    if (m["schema"] not in (SCHEMA, "PAPER_EPOCH_PERP_OPERATIONAL_V1") or m["strategy"] != "HYPERLIQUID_PAPER" or m["currency"] != "USDC"
            or m["cost_policy"] != "PERP_QUOTE_PLUS_CASH_COST_V2" or number(m["opening_cash"]) <= 0
            or integer(m["opened_at"]) == 0 or number(m["initial_net_r"]) != 0):
        raise ValueError("Explicit isolated USDC fixture inception required")
    if m["schema"] == "PAPER_EPOCH_PERP_OPERATIONAL_V1":
        from app.investment.quality_dips_operational_contract import hashed
        hashed(m["release"])
        if m["provenance"] != "ACCEPTED_PERP_PAPER_PARAMETERS_V1" or number(m["opening_cash"]) != 1000:
            raise ValueError("Distinct accepted perpetual parameters required")
    for k in ("epoch", "release", "provenance"): text(m[k])
    ZoneInfo(m["timezone"])
    p = m["perp_policy"]
    exact(p, "symbols max_positions max_leverage max_notional risk_limit session_stop participation maintenance_rate slippage_bps maker_bps taker_bps fee_schedule_id instrument_cut market_source funding_source")
    if (type(p["symbols"]) is not list or not p["symbols"] or len(set(p["symbols"])) != len(p["symbols"])
            or not set(p["symbols"]) <= {"BTC", "ETH", "SOL"} or not 1 <= integer(p["max_positions"]) <= 3
            or not 1 <= number(p["max_leverage"]) <= 50 or number(p["max_notional"]) <= 0
            or not 0 < number(p["risk_limit"]) <= 1 or number(p["session_stop"]) > -3
            or not 0 < number(p["participation"]) <= 1 or not 0 < number(p["maintenance_rate"]) < 1
            or min(number(p[k]) for k in ("slippage_bps", "maker_bps", "taker_bps")) < 0):
        raise ValueError("Bounded explicit perpetual policy required")
    for k in ("fee_schedule_id", "instrument_cut", "market_source", "funding_source"): text(p[k])


def refresh(m, s):
    for p in s["positions"].values():
        fresh = number(p["remaining"]) == 0 or p["mark_at"] == s["last_clock"]
        gain = (number(p["mark"]) - number(p["entry"])) * number(p["remaining"]) * (1 if p["side"] == "LONG" else -1)
        p.update(marked_notional=str(number(p["mark"]) * number(p["remaining"])) if fresh else None,
                 margin_equity=str(number(p["margin"]) + number(p["remaining_funding"]) + gain) if fresh else None,
                 maintenance_margin=str(maintenance(p, m["perp_policy"])) if fresh else None)
    live = [p for p in s["positions"].values() if number(p["remaining"]) > 0]
    s["reserved_margin"] = str(sum((number(p["margin"]) for p in live), number("0")))
    s["available_cash"] = str(number(s["cash"]) - number(s["reserved_margin"]))
    current = all(p["mark_at"] == s["last_clock"] for p in live)
    unrealized = sum(((number(p["mark"]) - number(p["entry"])) * number(p["remaining"])
                      * (1 if p["side"] == "LONG" else -1) for p in live), number("0"))
    required = sum((maintenance(p, m["perp_policy"])
                       for p in live), number("0"))
    s.update(unrealized=str(unrealized) if current else None,
             margin_equity=str(number(s["cash"]) + unrealized) if current else None,
             maintenance_margin=str(required) if current else None,
             valuation_state="CURRENT_SYNTHETIC_MARK" if current else "UNAVAILABLE",
             margin_warning=any(number(p["margin"]) + number(p["remaining_funding"]) + (number(p["mark"]) - number(p["entry"]))
                                * number(p["remaining"]) * (1 if p["side"] == "LONG" else -1)
                                <= maintenance(p, m["perp_policy"])
                                for p in live) if current else None)


def book(m, c, symbol, side):
    e, pol = c["evidence"], m["perp_policy"]
    exact(e, "source instrument_cut symbol observed_at sequence bid ask bid_size ask_size mark fee_schedule_id"
          + (" margin_policy" if c["schema"] in ("PAPER_PERP_MARGIN_ENTRY_V1", "PAPER_PERP_IOC_MARGIN_ENTRY_V1") else "")
          + (" ioc" if c["schema"] in ("PAPER_PERP_IOC_ENTRY_V1", "PAPER_PERP_IOC_MARGIN_ENTRY_V1") else "")
          + (" liquidation" if c["schema"] == "PAPER_PERP_LIQUIDATION_V1" else "")
          + (" maker_execution" if c["schema"] == "PAPER_PERP_MAKER_FILL_V1" else ""))
    if (e["source"] != pol["market_source"] or e["instrument_cut"] != pol["instrument_cut"]
            or e["fee_schedule_id"] != pol["fee_schedule_id"] or e["symbol"] != symbol
            or not 0 <= c["timestamp"] - integer(e["observed_at"]) <= 30
            or min(number(e[k]) for k in ("bid", "ask", "bid_size", "ask_size", "mark")) <= 0
            or number(e["bid"]) > number(e["ask"]) or c["liquidity"] not in ("MAKER", "TAKER")):
        raise ValueError("Fresh pinned executable book and fee evidence required")
    # Maker fills require a distinct queue/trade evidence model: never infer them
    # from resting quotes. Classification is explicit and unsupported fills refuse.
    if c["schema"] == "PAPER_PERP_MAKER_FILL_V1":
        if c["liquidity"] != "MAKER": raise ValueError("Maker classification required")
        proof = e["maker_execution"]
        exact(proof, "schema order_id limit_price rested_at queue_ahead traded_quantity trade_price trade_side trade_at source_ref requested_quantity filled_quantity cancelled_quantity")
        text(proof["order_id"])
        text(proof["source_ref"])
        buy = (side == "LONG") == (c["kind"] == "ENTRY")
        limit, traded = number(proof["limit_price"]), number(proof["trade_price"])
        requested, qty = number(proof["requested_quantity"]), number(c["quantity"])
        capacity = (number(proof["traded_quantity"]) - number(proof["queue_ahead"])) * number(pol["participation"])
        if (proof["schema"] != "SIMULATED_MAKER_QUEUE_FILL_V1" or limit <= 0 or traded <= 0
                or not integer(proof["rested_at"]) < integer(proof["trade_at"]) <= c["timestamp"]
                or c["timestamp"] - proof["trade_at"] > 30 or number(proof["queue_ahead"]) < 0
                or proof["trade_side"] != ("SELL" if buy else "BUY") or not (traded <= limit if buy else traded >= limit)
                or not 0 < qty <= min(requested, capacity) or number(proof["filled_quantity"]) != qty
                or number(proof["cancelled_quantity"]) != requested - qty
                or c["kind"] == "ENTRY" and (requested * limit > number(pol["max_notional"])
                                             or requested * number(c["risk_price"]) > number(pol["risk_limit"]))):
            raise ValueError("Accepted queue/trade-through/cancellation evidence required")
        return limit, digest([symbol, "MAKER_TRADE", proof["source_ref"]]), capacity
    if c["liquidity"] != "TAKER":
        raise ValueError("Maker execution evidence unavailable")
    text(e["sequence"])
    buy = (side == "LONG") == (c["kind"] == "ENTRY")
    field = "ask" if buy else "bid"
    qty = number(c["quantity"])
    key = digest([symbol, e["sequence"], field])
    if c["schema"] in ("PAPER_PERP_IOC_ENTRY_V1", "PAPER_PERP_IOC_MARGIN_ENTRY_V1"):
        proof = e["ioc"]
        exact(proof, "schema order_id requested_quantity filled_quantity cancelled_quantity quantity_step")
        text(proof["order_id"])
        step, requested = number(proof["quantity_step"]), number(proof["requested_quantity"])
        if (proof["schema"] != "PAPER_IOC_CANCEL_REMAINDER_V1" or step not in tuple(Decimal(10) ** -n for n in range(13))
                or requested <= 0 or (Fraction(requested) / Fraction(step)).denominator != 1):
            raise ValueError("Explicit IOC units and requested quantity required")
        available = min(requested, number(e[field + "_size"]) * number(pol["participation"]))
        units = Fraction(available) / Fraction(step)
        filled = step * (units.numerator // units.denominator)
        if (filled <= 0 or qty != filled or number(proof["filled_quantity"]) != filled
                or number(proof["cancelled_quantity"]) != requested - filled
                or requested * number(e[field]) > number(pol["max_notional"])
                or requested * number(c["risk_price"]) > number(pol["risk_limit"])):
            raise ValueError("IOC fill/cancellation/liquidity contradiction")
    if qty > number(e[field + "_size"]) * number(pol["participation"]):
        raise ValueError("Insufficient displayed liquidity")
    return number(e[field]), key, number(e[field + "_size"]) * number(pol["participation"])


def transition(m, s, c):
    common = "schema epoch operation_id kind expected_source_revision timestamp"
    kind = c.get("kind")
    recovery = c.get("schema") == "PAPER_PERP_FUNDING_RECOVERY_V1"
    tiered = c.get("schema") in ("PAPER_PERP_MARGIN_ENTRY_V1", "PAPER_PERP_MARGIN_MARK_V1", "PAPER_PERP_IOC_MARGIN_ENTRY_V1")
    expected_schema = {"ENTRY": "PAPER_PERP_MARGIN_ENTRY_V1", "MARK": "PAPER_PERP_MARGIN_MARK_V1"}.get(kind)
    extra = {"ENTRY": "symbol side quantity leverage risk_price origin_ref liquidity evidence",
             "EXIT": "position_id expected_position_revision quantity liquidity evidence",
             "FUNDING": "position_id expected_position_revision evidence",
             "MARK": "position_id expected_position_revision evidence"}.get(kind)
    if extra is None:
        raise ValueError("Unsupported perpetual event; liquidation requires separate authenticated execution contract")
    exact(c, common + " " + extra + (" recovery" if recovery else ""))
    ioc = c.get("schema") in ("PAPER_PERP_IOC_ENTRY_V1", "PAPER_PERP_IOC_MARGIN_ENTRY_V1")
    liquidation = c.get("schema") == "PAPER_PERP_LIQUIDATION_V1"
    maker = c.get("schema") == "PAPER_PERP_MAKER_FILL_V1"
    if (c["schema"] != ("PAPER_PERP_MAKER_FILL_V1" if maker else "PAPER_PERP_LIQUIDATION_V1" if liquidation else c["schema"] if ioc else "PAPER_PERP_FUNDING_RECOVERY_V1" if recovery else expected_schema if tiered else "PAPER_PERP_COMMAND_V2")
            or maker and kind not in ("ENTRY", "EXIT")
            or liquidation and kind != "EXIT"
            or ioc and kind != "ENTRY"
            or recovery and kind != "FUNDING" or c["epoch"] != m["epoch"]
            or integer(c["expected_source_revision"]) != s["revision"]
            or integer(c["timestamp"]) < s["last_clock"]):
        raise ValueError("Stale perpetual command")
    text(c["operation_id"])
    pol = m["perp_policy"]
    if kind == "ENTRY":
        qty, lev, risk = number(c["quantity"]), number(c["leverage"]), number(c["risk_price"])
        if (c["symbol"] not in pol["symbols"] or c["side"] not in ("LONG", "SHORT") or qty <= 0
                or not 1 <= lev <= number(pol["max_leverage"]) or risk <= 0 or risk * qty > number(pol["risk_limit"])
                or Fraction(int(s["net_r_fraction"]["numerator"]), int(s["net_r_fraction"]["denominator"])) <= Fraction(number(pol["session_stop"]))
                or sum(number(p["remaining"]) > 0 for p in s["positions"].values()) >= pol["max_positions"]
                or any(p["origin_ref"] == c["origin_ref"] or (p["symbol"] == c["symbol"] and number(p["remaining"]) > 0)
                       for p in s["positions"].values())):
            raise ValueError("Perpetual entry risk restriction")
        text(c["origin_ref"])
        ident = m["epoch"] + ":" + digest([m["epoch"], c["operation_id"]])
        price, key, capacity = book(m, c, c["symbol"], c["side"])
        if ioc and (c["origin_ref"] != c["evidence"]["ioc"]["order_id"]
                    or any(old.get("ioc", {}).get("order_id") == c["evidence"]["ioc"]["order_id"] for old in s["positions"].values())):
            raise ValueError("IOC order identity already consumed or substituted")
        if maker and c["origin_ref"] != c["evidence"]["maker_execution"]["order_id"]:
            raise ValueError("Maker order identity substitution")
        notional = qty * price
        margin = notional / lev
        margin_basis = max(price, number(c["evidence"]["mark"])) if maker or tiered else price
        if maker or tiered: margin = qty * margin_basis / lev
        if notional > number(pol["max_notional"]) or not tiered and margin <= qty * number(c["evidence"]["mark"]) * number(pol["maintenance_rate"]):
            raise ValueError("Notional or maintenance restriction")
        p = {"symbol": c["symbol"], "side": c["side"], "entry": str(price), "quantity": str(qty), "remaining": str(qty),
                 "margin": str(margin), "leverage": str(lev), "entry_notional": str(notional), "risk_price": str(risk),
                 "revision": 0, "origin_ref": c["origin_ref"], "realized_net": "0", "funding": "0", "remaining_funding": "0", "fees": "0", "slippage": "0",
                 "next_funding": (c["timestamp"] // 3600 + 1) * 3600, "mark": c["evidence"]["mark"], "mark_at": c["timestamp"]}
        s["positions"][ident] = p
        if maker or tiered: p["margin_basis_price"] = str(margin_basis)
        if ioc:
            p["ioc"] = copy.deepcopy(c["evidence"]["ioc"])
        if tiered:
            policy = c["evidence"]["margin_policy"]
            required, tier_limit = tier_requirement(policy, qty * number(p["mark"]), pol["instrument_cut"])
            if lev > tier_limit or margin <= required:
                raise ValueError("Accepted tier leverage/maintenance exceeded")
            p["margin_policy"] = copy.deepcopy(policy)
    else:
        ident = c["position_id"]
        p = s["positions"].get(ident)
        if not p or number(p["remaining"]) <= 0 or integer(c["expected_position_revision"]) != p["revision"]:
            raise ValueError("Unknown, closed or stale position")
    delta, gain, fee, slip, liquidation_fee = (number("0") for _ in range(5))
    if kind in ("ENTRY", "EXIT"):
        if c["timestamp"] % 3600 == 0 or (kind == "EXIT" and p["next_funding"] <= c["timestamp"]):
            raise ValueError("Missing funding or ambiguous settlement ordering")
        qty = number(c["quantity"])
        if qty <= 0 or qty > number(p["remaining"]):
            raise ValueError("Invalid partial quantity")
        if kind == "EXIT":
            price, key, capacity = book(m, c, p["symbol"], p["side"])
            if liquidation:
                proof = c["evidence"]["liquidation"]
                exact(proof, "schema source_cut execution_ref trigger_mark maintenance equity quantity fee_bps fee_schedule_id action")
                text(proof["execution_ref"])
                text(proof["fee_schedule_id"])
                mark = number(proof["trigger_mark"])
                marked = {**p, "mark": str(mark)}
                required = maintenance(marked, pol)
                equity = number(p["margin"]) + number(p["remaining_funding"]) + (mark - number(p["entry"])) * number(p["remaining"]) * (1 if p["side"] == "LONG" else -1)
                if (proof["schema"] != "SIMULATED_BOOK_LIQUIDATION_V1" or proof["source_cut"] != pol["instrument_cut"]
                        or mark != number(c["evidence"]["mark"]) or number(proof["quantity"]) != qty
                        or number(proof["maintenance"]) != required or number(proof["equity"]) != equity
                        or equity > required or not 0 <= number(proof["fee_bps"]) <= 10000
                        or proof["action"] != ("FULL_BOOK_CLOSE" if qty == number(p["remaining"]) else "PARTIAL_BOOK_CLOSE")):
                    raise ValueError("Complete simulated liquidation trigger/fee/execution evidence required")
                liquidation_fee = price * qty * number(proof["fee_bps"]) / 10000
                s["liquidation_fees"] = str(number(s.get("liquidation_fees", "0")) + liquidation_fee)
                p["liquidation_fees"] = str(number(p.get("liquidation_fees", "0")) + liquidation_fee)
            gain = (price - number(p["entry"])) * qty * (1 if p["side"] == "LONG" else -1)
            released = number(p["margin"]) if qty == number(p["remaining"]) else number(p.get("margin_basis_price", p["entry"])) * qty / number(p["leverage"])
            remaining_funding = number("0") if qty == number(p["remaining"]) else number(p["remaining_funding"]) * (number(p["remaining"]) - qty) / number(p["remaining"])
            p.update(remaining=str(number(p["remaining"]) - qty), margin=str(number(p["margin"]) - released),
                     remaining_funding=str(remaining_funding),
                     mark=c["evidence"]["mark"], mark_at=c["timestamp"])
        used = s["liquidity_consumption"].get(key, {"digest": digest(c["evidence"]), "quantity": "0"})
        if used["digest"] != digest(c["evidence"]) or number(used["quantity"]) + qty > capacity:
            raise ValueError("Reused or conflicting book liquidity")
        s["liquidity_consumption"][key] = {"digest": used["digest"], "quantity": str(number(used["quantity"]) + qty)}
        fee = price * qty * number(pol["maker_bps"] if maker else pol["taker_bps"]) / 10000 + liquidation_fee
        slip = price * qty * number(pol["slippage_bps"]) / 10000
        delta = gain - fee - slip
        if maker:
            order = c["evidence"]["maker_execution"]["order_id"]
            orders = s.setdefault("maker_orders", {})
            if order in orders: raise ValueError("Maker order already consumed; no callback replay")
            orders[order] = digest(c)
    elif kind == "FUNDING":
        e = c["evidence"]
        exact(e, "source symbol settlement_at interval_seconds rate oracle source_id")
        at = integer(e["settlement_at"])
        if (e["source"] != pol["funding_source"] or e["symbol"] != p["symbol"]
                or at != p["next_funding"] or at % 3600 or integer(e["interval_seconds"]) != 3600
                or not at <= c["timestamp"] or not recovery and c["timestamp"] > at + 30 or number(e["oracle"]) <= 0
                or abs(number(e["rate"])) > number("0.04")):
            raise ValueError("Complete ordered hourly funding evidence required")
        text(e["source_id"])
        if recovery:
            proof = c["recovery"]
            exact(proof, "authority_ref state_digest evidence_digest quantity accepted_at")
            text(proof["authority_ref"])
            if (proof["state_digest"] != digest(s) or proof["evidence_digest"] != digest(e)
                    or number(proof["quantity"]) != number(p["remaining"])
                    or integer(proof["accepted_at"]) != c["timestamp"]):
                raise ValueError("Exact recovery source/quantity/evidence binding required")
        delta = -number(p["remaining"]) * number(e["oracle"]) * number(e["rate"]) * (1 if p["side"] == "LONG" else -1)
        s["funding"] = str(number(s["funding"]) + delta)
        p.update(funding=str(number(p["funding"]) + delta),
                 remaining_funding=str(number(p["remaining_funding"]) + delta), next_funding=at + 3600)
    else:
        e = c["evidence"]
        exact(e, "source instrument_cut symbol observed_at mark source_id" + (" margin_policy" if tiered else ""))
        if (e["source"] != pol["market_source"] or e["instrument_cut"] != pol["instrument_cut"]
                or e["symbol"] != p["symbol"] or not 0 <= c["timestamp"] - integer(e["observed_at"]) <= 30
                or number(e["mark"]) <= 0 or p["next_funding"] <= c["timestamp"]):
            raise ValueError("Fresh mark and complete funding required")
        text(e["source_id"])
        if tiered:
            tier_requirement(e["margin_policy"], number(e["mark"]) * number(p["remaining"]), pol["instrument_cut"])
            p["margin_policy"] = copy.deepcopy(e["margin_policy"])
        p.update(mark=e["mark"], mark_at=c["timestamp"])
    p.update(revision=p["revision"] + 1, realized_net=str(number(p["realized_net"]) + delta),
             fees=str(number(p["fees"]) + fee), slippage=str(number(p["slippage"]) + slip))
    prior = s["net_r_fraction"]
    ratio = Fraction(int(prior["numerator"]), int(prior["denominator"])) + Fraction(delta) / Fraction(number(p["risk_price"]) * number(p["quantity"]))
    # Only this explicitly non-authoritative display may round. Risk admission
    # above compares the exact rational, never the rounded presentation string.
    with localcontext() as display:
        display.traps[Inexact] = False
        shown = str(Decimal(ratio.numerator) / Decimal(ratio.denominator))
    s.update(cash=str(number(s["cash"]) + delta), gross=str(number(s["gross"]) + gain),
             fees=str(number(s["fees"]) + fee), slippage=str(number(s["slippage"]) + slip),
             costs=str(number(s["costs"]) + fee + slip), net=str(number(s["net"]) + delta),
             net_r=shown, net_r_fraction={"numerator": str(ratio.numerator), "denominator": str(ratio.denominator)},
             revision=s["revision"] + 1, last_clock=c["timestamp"])
    refresh(m, s)
    if liquidation and number(s["cash"]) < 0:
        raise ValueError("Bankruptcy/backstop authority unavailable")
    if kind == "ENTRY" and number(s["available_cash"]) < 0:
        raise ValueError("Insufficient available collateral")
    return {"schema": "PAPER_PERP_RECEIPT_V2", "epoch": m["epoch"], "operation_id": c["operation_id"],
                "payload_digest": digest(c), "source_revision": s["revision"], "position_id": ident,
                "position_revision": p["revision"], "state_digest": digest(s), "execution": "SIMULATED",
                "production_authorized": False, "startup_authorized": False}
