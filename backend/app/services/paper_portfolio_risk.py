"""Pure multi-market admission checks, not a ledger or an authorization issuer.

USD cash and USDC collateral remain separate. An accepted conversion/reservation
port must supply USD risk equivalents; this module never assumes USD == USDC.
The legacy perp R journal is insufficient evidence of margin/funding accounting.
"""

from decimal import ROUND_HALF_EVEN, Context, Decimal, DecimalException, Inexact, localcontext

from app.services.paper_financial_replay import number, text

LANES = ("QUALITY_DIPS", "HYPERLIQUID")


def _amount(row, key, *, positive=False):
    value = number(row[key])
    if value < 0 or positive and value == 0:
        raise ValueError("PORTFOLIO_INVALID_AMOUNT")
    return value


def check_portfolio_cut(policy, accounts, *, now):
    """Validate a complete independently verified cut under an explicit policy.

    Evidence authentication and exclusive cross-process admission belong to the
    caller's accepted custody lease. Passing this pure check grants no authority.
    Exposure uses gross notional, never netting stock and perp positions.
    """
    try:
        with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)) as ctx:
            ctx.traps[Inexact] = True  # Never round a limit violation into admission.
            return _check(policy, accounts, now)
    except DecimalException as error:
        raise ValueError("PORTFOLIO_INEXACT_OR_INVALID_FINANCIAL_EVIDENCE") from error


def _check(policy, accounts, now, *, closing=False):
    if (type(now) is not int or now <= 0 or type(policy) is not dict
            or set(policy) != {"schema", "policy_id", "capital_usd", "max_gross_usd",
                               "max_loss_usd", "max_positions", "allocations", "max_age", "max_perp_leverage"}
            or policy["schema"] != "ATLAS_PAPER_PORTFOLIO_RISK_V1"
            or type(policy["max_positions"]) is not int or not 1 <= policy["max_positions"] <= 4
            or type(policy["max_age"]) is not int or not 0 < policy["max_age"] <= 30
            or type(accounts) is not list or len(accounts) != 2
            or type(policy["allocations"]) is not dict or set(policy["allocations"]) != set(LANES)):
        raise ValueError("PORTFOLIO_EXPLICIT_COMPLETE_POLICY_REQUIRED")
    text(policy["policy_id"])
    capital = _amount(policy, "capital_usd", positive=True)
    gross_limit = _amount(policy, "max_gross_usd", positive=True)
    loss_limit = _amount(policy, "max_loss_usd", positive=True)
    leverage_limit = _amount(policy, "max_perp_leverage", positive=True)
    if leverage_limit < 1 or leverage_limit != leverage_limit.to_integral_value():
        raise ValueError("PORTFOLIO_EXPLICIT_LEVERAGE_LIMIT_REQUIRED")
    allocations = {lane: _amount(policy["allocations"], lane) for lane in LANES}
    if sum(allocations.values()) > capital:
        raise ValueError("PORTFOLIO_CAPITAL_ALLOCATED_TWICE")
    lanes, epochs, positions, instruments = set(), set(), set(), set()
    gross, risk, count = Decimal(0), Decimal(0), 0
    cuts = {}
    for account in accounts:
        if (type(account) is not dict or set(account) != {
                "schema", "lane", "epoch", "currency", "revision", "head", "at", "state",
                "allocated_usd", "committed_usd", "positions", "pending_operations", "conversion_id"}
                or account["schema"] != "ATLAS_PAPER_RISK_CUT_V1"
                or account["lane"] not in LANES or account["lane"] in lanes
                or account["epoch"] in epochs or account["state"] != "ACKNOWLEDGED"
                or account["pending_operations"] != []
                or type(account["revision"]) is not int or account["revision"] < 0
                or type(account["at"]) is not int or not 0 <= now - account["at"] <= policy["max_age"]
                or type(account["positions"]) is not list):
            raise ValueError("PORTFOLIO_INCOMPLETE_OR_UNKNOWN_CUT")
        lane = account["lane"]
        for key in ("epoch", "head", "conversion_id"):
            text(account[key])
        if account["currency"] != ("USD" if lane == "QUALITY_DIPS" else "USDC"):
            raise ValueError("PORTFOLIO_CURRENCY_SUBSTITUTION")
        if (_amount(account, "allocated_usd") != allocations[lane]
                or _amount(account, "committed_usd") > allocations[lane]):
            raise ValueError("PORTFOLIO_ACCOUNT_ALLOCATION_MISMATCH")
        lanes.add(lane)
        epochs.add(account["epoch"])
        cuts[lane] = {"epoch": account["epoch"], "revision": account["revision"], "head": account["head"]}
        lane_committed = Decimal(0)
        for position in account["positions"]:
            required = {"id", "instrument_id", "side", "quantity", "gross_usd", "loss_usd", "reserved_usd", "derivatives"}
            if (type(position) is not dict or set(position) != required
                    or position["side"] not in ("LONG", "SHORT")):
                raise ValueError("PORTFOLIO_POSITION_EVIDENCE_REQUIRED")
            for key in ("id", "instrument_id"):
                text(position[key])
            if (position["id"] in positions or position["instrument_id"] in instruments
                    or not position["id"].startswith(account["epoch"] + ":")):
                raise ValueError("PORTFOLIO_DUPLICATE_OR_CONFLICTING_POSITION")
            positions.add(position["id"])
            instruments.add(position["instrument_id"])
            _amount(position, "quantity", positive=True)
            exposure = _amount(position, "gross_usd", positive=True)
            loss = _amount(position, "loss_usd", positive=True)
            reserved = _amount(position, "reserved_usd", positive=True)
            if lane == "QUALITY_DIPS":
                if (position["side"] != "LONG" or position["derivatives"] is not None
                        or (not closing and (exposure > 100 or reserved < exposure))
                        or len(account["positions"]) > 1):
                    raise ValueError("PORTFOLIO_STOCK_LIMIT")
            else:
                _perp(position["derivatives"], leverage_limit, closing=closing)
                if len(account["positions"]) > 3 or not closing and loss > 1:
                    raise ValueError("PORTFOLIO_EXISTING_PERP_RISK_LIMIT")
            gross += exposure
            risk += loss
            lane_committed += reserved
            count += 1
        if lane_committed != number(account["committed_usd"]):
            raise ValueError("PORTFOLIO_COMMITTED_CAPITAL_MISMATCH")
    if not closing and (gross > gross_limit or risk > loss_limit or count > policy["max_positions"]):
        raise ValueError("PORTFOLIO_GLOBAL_LIMIT")
    return {"schema": "ATLAS_PAPER_PORTFOLIO_CUT_V1", "policy_id": policy["policy_id"],
            "cuts": cuts, "gross_usd": str(gross), "loss_usd": str(risk), "positions": count,
            "total_cash": None, "total_equity": None, "startup_authorized": False}


def _perp(row, leverage_limit, *, closing=False):
    if (type(row) is not dict or set(row) != {
            "schema", "margin_mode", "leverage", "max_leverage", "notional", "collateral",
            "maintenance_margin", "unrealized_pnl", "funding_cash", "fees_cash", "slippage_cash",
            "equity", "stress_loss_cash", "funding_complete", "fee_schedule_id", "funding_cut", "mark_id", "book_id"}
            or row["schema"] != "ATLAS_PERP_RISK_EVIDENCE_V1"
            or row["margin_mode"] != "ISOLATED" or row["funding_complete"] is not True):
        raise ValueError("PERP_MARGIN_AND_FUNDING_EVIDENCE_REQUIRED")
    for key in ("fee_schedule_id", "funding_cut", "mark_id", "book_id"):
        text(row[key])
    leverage = _amount(row, "leverage", positive=True)
    venue_limit = _amount(row, "max_leverage", positive=True)
    if (leverage != leverage.to_integral_value() or leverage < 1
            or venue_limit != venue_limit.to_integral_value()
            or not closing and leverage > min(leverage_limit, venue_limit)):
        raise ValueError("PERP_UNSUPPORTED_LEVERAGE")
    notional = _amount(row, "notional", positive=True)
    collateral = _amount(row, "collateral", positive=True)
    maintenance = _amount(row, "maintenance_margin", positive=True)
    fees, slippage = _amount(row, "fees_cash"), _amount(row, "slippage_cash")
    # Native collateral stress is USDC; never subtract USD portfolio loss here.
    stress_loss = _amount(row, "stress_loss_cash", positive=True)
    if not closing and stress_loss > 1:
        raise ValueError("PERP_NATIVE_CURRENCY_RISK_LIMIT")
    # Funding cash is signed: positive means received, negative means paid.
    equity = collateral + number(row["unrealized_pnl"]) + number(row["funding_cash"]) - fees - slippage
    if (number(row["equity"]) != equity or not closing and (collateral * leverage < notional
            or maintenance >= collateral or equity - stress_loss <= maintenance)):
        raise ValueError("PERP_MARGIN_OR_LIQUIDATION_BUFFER_INSUFFICIENT")


def check_portfolio_reducing_exit(policy, before, after, *, now):
    """Only an authenticated EXIT may use this paired reduction proof.

    Entry admission still enforces the explicit $100 cap unchanged. A previously
    acknowledged position whose market value grew past that entry cap must remain
    closable. This check cannot add an identity, increase quantity or exposure,
    reverse side, release an UNKNOWN cut or authorize any financial operation.
    """
    try:
        with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)) as ctx:
            ctx.traps[Inexact] = True
            _check(policy, before, now, closing=True)
            result = _check(policy, after, now, closing=True)
            old_accounts = {a["lane"]: a for a in before}
            for account in after:
                old = old_accounts[account["lane"]]
                if (any(account[k] != old[k] for k in ("epoch", "currency", "allocated_usd", "conversion_id"))
                        or number(account["committed_usd"]) > number(old["committed_usd"])):
                    raise ValueError("PORTFOLIO_EXIT_ACCOUNT_SUBSTITUTION")
                originals = {p["id"]: p for p in old["positions"]}
                for p in account["positions"]:
                    original = originals.get(p["id"])
                    if (original is None or any(p[k] != original[k] for k in ("instrument_id", "side"))
                            or any(number(p[k]) > number(original[k]) for k in
                                   ("quantity", "gross_usd", "loss_usd", "reserved_usd"))):
                        raise ValueError("PORTFOLIO_EXIT_MUST_ONLY_REDUCE")
            return result
    except DecimalException as error:
        raise ValueError("PORTFOLIO_INEXACT_EXIT_EVIDENCE") from error
