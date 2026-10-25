"""V2 perpetual arithmetic inside FS1, not a ledger or source authenticator.

This schema is disposable-only. Evidence identities are pinned simulation inputs;
they confer neither provider authenticity nor operational trading authority.
Quotes are unadjusted book prices. Slippage is a separate cash charge, once.
Funding uses explicit hourly oracle settlement, never an assumed zero rate.
Margin is an initial risk reservation, not exchange withdrawable margin. Fees
are cash-paid; settled funding is allocated to remaining-position mark risk.
Cross-margin, automatic margin top-ups and exchange margin tiers are unsupported.
"""
from decimal import Decimal, Inexact, localcontext
from fractions import Fraction
from zoneinfo import ZoneInfo

from app.services.paper_financial_replay import digest, number, text

SCHEMA = "PAPER_EPOCH_PERP_FIXTURE_V2"


def exact(value, fields):
    if type(value) is not dict or set(value) != set(fields.split()):
        raise ValueError("Exact perpetual evidence schema required")


def integer(value):
    if type(value) is not int or value < 0:
        raise ValueError("Nonnegative integer evidence required")
    return value


def validate_manifest(m):
    exact(m, "schema epoch strategy currency opening_cash opened_at timezone release provenance initial_net_r cost_policy perp_policy")
    if (m["schema"] != SCHEMA or m["strategy"] != "HYPERLIQUID_PAPER" or m["currency"] != "USDC"
            or m["cost_policy"] != "PERP_QUOTE_PLUS_CASH_COST_V2" or number(m["opening_cash"]) <= 0
            or integer(m["opened_at"]) == 0 or number(m["initial_net_r"]) != 0):
        raise ValueError("Explicit isolated USDC fixture inception required")
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
                 maintenance_margin=str(number(p["mark"]) * number(p["remaining"]) * number(m["perp_policy"]["maintenance_rate"])) if fresh else None)
    live = [p for p in s["positions"].values() if number(p["remaining"]) > 0]
    s["reserved_margin"] = str(sum((number(p["margin"]) for p in live), number("0")))
    s["available_cash"] = str(number(s["cash"]) - number(s["reserved_margin"]))
    current = all(p["mark_at"] == s["last_clock"] for p in live)
    unrealized = sum(((number(p["mark"]) - number(p["entry"])) * number(p["remaining"])
                      * (1 if p["side"] == "LONG" else -1) for p in live), number("0"))
    maintenance = sum((number(p["mark"]) * number(p["remaining"]) * number(m["perp_policy"]["maintenance_rate"])
                       for p in live), number("0"))
    s.update(unrealized=str(unrealized) if current else None,
             margin_equity=str(number(s["cash"]) + unrealized) if current else None,
             maintenance_margin=str(maintenance) if current else None,
             valuation_state="CURRENT_SYNTHETIC_MARK" if current else "UNAVAILABLE",
             margin_warning=any(number(p["margin"]) + number(p["remaining_funding"]) + (number(p["mark"]) - number(p["entry"]))
                                * number(p["remaining"]) * (1 if p["side"] == "LONG" else -1)
                                <= number(p["mark"]) * number(p["remaining"]) * number(m["perp_policy"]["maintenance_rate"])
                                for p in live) if current else None)


def book(m, c, symbol, side):
    e, pol = c["evidence"], m["perp_policy"]
    exact(e, "source instrument_cut symbol observed_at sequence bid ask bid_size ask_size mark fee_schedule_id")
    if (e["source"] != pol["market_source"] or e["instrument_cut"] != pol["instrument_cut"]
            or e["fee_schedule_id"] != pol["fee_schedule_id"] or e["symbol"] != symbol
            or not 0 <= c["timestamp"] - integer(e["observed_at"]) <= 30
            or min(number(e[k]) for k in ("bid", "ask", "bid_size", "ask_size", "mark")) <= 0
            or number(e["bid"]) > number(e["ask"]) or c["liquidity"] not in ("MAKER", "TAKER")):
        raise ValueError("Fresh pinned executable book and fee evidence required")
    # Maker fills require a distinct queue/trade evidence model: never infer them
    # from resting quotes. Classification is explicit and unsupported fills refuse.
    if c["liquidity"] != "TAKER":
        raise ValueError("Maker execution evidence unavailable")
    text(e["sequence"])
    buy = (side == "LONG") == (c["kind"] == "ENTRY")
    field = "ask" if buy else "bid"
    qty = number(c["quantity"])
    key = digest([symbol, e["sequence"], field])
    if qty > number(e[field + "_size"]) * number(pol["participation"]):
        raise ValueError("Insufficient displayed liquidity")
    return number(e[field]), key, number(e[field + "_size"]) * number(pol["participation"])


def transition(m, s, c):
    common = "schema epoch operation_id kind expected_source_revision timestamp"
    kind = c.get("kind")
    extra = {"ENTRY": "symbol side quantity leverage risk_price origin_ref liquidity evidence",
             "EXIT": "position_id expected_position_revision quantity liquidity evidence",
             "FUNDING": "position_id expected_position_revision evidence",
             "MARK": "position_id expected_position_revision evidence"}.get(kind)
    if extra is None:
        raise ValueError("Unsupported perpetual event; liquidation requires separate authenticated execution contract")
    exact(c, common + " " + extra)
    if (c["schema"] != "PAPER_PERP_COMMAND_V2" or c["epoch"] != m["epoch"]
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
        notional = qty * price
        margin = notional / lev
        if notional > number(pol["max_notional"]) or margin <= qty * number(c["evidence"]["mark"]) * number(pol["maintenance_rate"]):
            raise ValueError("Notional or maintenance restriction")
        p = {"symbol": c["symbol"], "side": c["side"], "entry": str(price), "quantity": str(qty), "remaining": str(qty),
                 "margin": str(margin), "leverage": str(lev), "entry_notional": str(notional), "risk_price": str(risk),
                 "revision": 0, "origin_ref": c["origin_ref"], "realized_net": "0", "funding": "0", "remaining_funding": "0", "fees": "0", "slippage": "0",
                 "next_funding": (c["timestamp"] // 3600 + 1) * 3600, "mark": c["evidence"]["mark"], "mark_at": c["timestamp"]}
        s["positions"][ident] = p
    else:
        ident = c["position_id"]
        p = s["positions"].get(ident)
        if not p or number(p["remaining"]) <= 0 or integer(c["expected_position_revision"]) != p["revision"]:
            raise ValueError("Unknown, closed or stale position")
    delta, gain, fee, slip = number("0"), number("0"), number("0"), number("0")
    if kind in ("ENTRY", "EXIT"):
        if c["timestamp"] % 3600 == 0 or (kind == "EXIT" and p["next_funding"] <= c["timestamp"]):
            raise ValueError("Missing funding or ambiguous settlement ordering")
        qty = number(c["quantity"])
        if qty <= 0 or qty > number(p["remaining"]):
            raise ValueError("Invalid partial quantity")
        if kind == "EXIT":
            price, key, capacity = book(m, c, p["symbol"], p["side"])
            gain = (price - number(p["entry"])) * qty * (1 if p["side"] == "LONG" else -1)
            released = number(p["margin"]) if qty == number(p["remaining"]) else number(p["entry"]) * qty / number(p["leverage"])
            remaining_funding = number("0") if qty == number(p["remaining"]) else number(p["remaining_funding"]) * (number(p["remaining"]) - qty) / number(p["remaining"])
            p.update(remaining=str(number(p["remaining"]) - qty), margin=str(number(p["margin"]) - released),
                     remaining_funding=str(remaining_funding),
                     mark=c["evidence"]["mark"], mark_at=c["timestamp"])
        used = s["liquidity_consumption"].get(key, {"digest": digest(c["evidence"]), "quantity": "0"})
        if used["digest"] != digest(c["evidence"]) or number(used["quantity"]) + qty > capacity:
            raise ValueError("Reused or conflicting book liquidity")
        s["liquidity_consumption"][key] = {"digest": used["digest"], "quantity": str(number(used["quantity"]) + qty)}
        fee = price * qty * number(pol["taker_bps"]) / 10000
        slip = price * qty * number(pol["slippage_bps"]) / 10000
        delta = gain - fee - slip
    elif kind == "FUNDING":
        e = c["evidence"]
        exact(e, "source symbol settlement_at interval_seconds rate oracle source_id")
        at = integer(e["settlement_at"])
        if (e["source"] != pol["funding_source"] or e["symbol"] != p["symbol"]
                or at != p["next_funding"] or at % 3600 or integer(e["interval_seconds"]) != 3600
                or not at <= c["timestamp"] <= at + 30 or number(e["oracle"]) <= 0
                or abs(number(e["rate"])) > number("0.04")):
            raise ValueError("Complete ordered hourly funding evidence required")
        text(e["source_id"])
        delta = -number(p["remaining"]) * number(e["oracle"]) * number(e["rate"]) * (1 if p["side"] == "LONG" else -1)
        s["funding"] = str(number(s["funding"]) + delta)
        p.update(funding=str(number(p["funding"]) + delta),
                 remaining_funding=str(number(p["remaining_funding"]) + delta), next_funding=at + 3600)
    else:
        e = c["evidence"]
        exact(e, "source instrument_cut symbol observed_at mark source_id")
        if (e["source"] != pol["market_source"] or e["instrument_cut"] != pol["instrument_cut"]
                or e["symbol"] != p["symbol"] or not 0 <= c["timestamp"] - integer(e["observed_at"]) <= 30
                or number(e["mark"]) <= 0 or p["next_funding"] <= c["timestamp"]):
            raise ValueError("Fresh mark and complete funding required")
        text(e["source_id"])
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
    if kind == "ENTRY" and number(s["available_cash"]) < 0:
        raise ValueError("Insufficient available collateral")
    return {"schema": "PAPER_PERP_RECEIPT_V2", "epoch": m["epoch"], "operation_id": c["operation_id"],
                "payload_digest": digest(c), "source_revision": s["revision"], "position_id": ident,
                "position_revision": p["revision"], "state_digest": digest(s), "execution": "SIMULATED",
                "production_authorized": False, "startup_authorized": False}
