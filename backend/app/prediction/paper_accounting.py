"""Pure supplied-record arithmetic. No provider, journal or execution authority."""
from __future__ import annotations

from decimal import Decimal, DecimalException

VERSION = "prediction-paper-accounting-v1"


class AccountingEvidenceError(ValueError):
    """Required financial evidence is absent or contradictory."""


def parse_decimal(value):
    if value is None or type(value) is bool:
        return None
    try:
        text = str(value)
        if not text or len(text) > 128:
            return None
        number = Decimal(text)
        if not number.is_finite() or abs(number.adjusted()) > 100:
            return None
        return number
    except (DecimalException, ValueError, TypeError):
        return None


def require_number(value, field, *, minimum=None, maximum=None, positive=False):
    number = parse_decimal(value)
    if number is None or (positive and number <= 0) or (minimum is not None and number < minimum) or (maximum is not None and number > maximum):
        raise AccountingEvidenceError("MISSING_OR_INVALID_" + field.upper())
    return number


def near(left, right):
    # Explicit arithmetic tolerance, not a price/slippage/fee assumption.
    return abs(left - right) <= Decimal("0.00000001")


def validate_fill(fill, quantity):
    if type(fill) is not dict or fill.get("fillable") is not True:
        raise AccountingEvidenceError("FILL_NOT_CONFIRMED")
    quantity = require_number(quantity, "quantity_contracts", positive=True)
    price = require_number(fill.get("vwap_dollars"), "vwap_dollars", minimum=0, maximum=1)
    notional = require_number(fill.get("notional_dollars"), "notional_dollars", minimum=0)
    fee = require_number(fill.get("estimated_taker_fee_dollars"), "estimated_taker_fee_dollars", minimum=0)
    levels = fill.get("levels")
    if type(levels) is not list or not 1 <= len(levels) <= 10000:
        raise AccountingEvidenceError("MISSING_OR_INVALID_FILL_LEVELS")
    filled = Decimal(0); cost = Decimal(0); level_fees = []
    try:
        for row in levels:
            if type(row) is not dict:
                raise AccountingEvidenceError("INVALID_FILL_LEVEL")
            p = require_number(row.get("price_dollars"), "level_price", minimum=0, maximum=1)
            q = require_number(row.get("quantity_contracts"), "level_quantity", positive=True)
            filled += q; cost += q*p
            if row.get("estimated_taker_fee_dollars") is not None:
                level_fees.append(require_number(row["estimated_taker_fee_dollars"], "level_fee", minimum=0))
        if not near(filled, quantity) or not near(cost, notional) or not near(quantity*price, notional):
            raise AccountingEvidenceError("CONTRADICTORY_FILL_QUANTITY_OR_NOTIONAL")
        for key in ("requested_quantity", "filled_quantity"):
            if key in fill and not near(require_number(fill[key], key, positive=True), quantity):
                raise AccountingEvidenceError("CONTRADICTORY_" + key.upper())
        if len(level_fees) == len(levels) and not near(sum(level_fees, Decimal(0)), fee):
            raise AccountingEvidenceError("CONTRADICTORY_FILL_FEES")
    except DecimalException as error:
        raise AccountingEvidenceError("UNSUPPORTED_FINANCIAL_RANGE") from error
    return {"quantity":quantity, "price":price, "notional":notional, "fee":fee}


def calculate_close(opened, exit_price, exit_fee):
    errors = []; warnings = []; values = {}
    for key, options in (("quantity_contracts", {"positive":True}), ("actual_entry_price", {"minimum":0,"maximum":1}), ("entry_fee_dollars", {"minimum":0})):
        try:
            values[key] = require_number(opened.get(key), key, **options)
        except AccountingEvidenceError as error:
            errors.append(str(error)); values[key] = None
    quantity, entry, fee = (values[k] for k in ("quantity_contracts", "actual_entry_price", "entry_fee_dollars"))
    if opened.get("entry_notional_dollars") is None:
        warnings.append("ENTRY_NOTIONAL_NOT_RECORDED")
    elif quantity is not None and entry is not None:
        recorded = parse_decimal(opened["entry_notional_dollars"])
        if recorded is None or recorded < 0 or not near(recorded, entry*quantity):
            errors.append("CONTRADICTORY_ENTRY_NOTIONAL"); entry = None
    gross = net = roi = None
    try:
        if quantity is not None and entry is not None:
            gross = (exit_price-entry)*quantity
            if fee is not None:
                net = gross-fee-exit_fee
                basis = entry*quantity+fee
                if basis > 0:
                    roi = net/basis
                else:
                    warnings.append("ZERO_COST_BASIS_ROI_UNDEFINED")
        if any(value is not None and (not value.is_finite() or abs(value.adjusted()) > 100) for value in (gross,net,roi)):
            raise AccountingEvidenceError("UNSUPPORTED_FINANCIAL_RANGE")
    except (DecimalException, AccountingEvidenceError):
        errors.append("UNSUPPORTED_FINANCIAL_RANGE"); gross = net = roi = None
    return {"gross":gross,"net":net,"roi":roi,"issues":sorted(set(errors)),"warnings":warnings}


def audit_close(opened, closed):
    issues = []; warnings = []
    if opened is None:
        return {"version":VERSION,"status":"INSUFFICIENT_EVIDENCE","issues":["MISSING_SOURCE_OPEN"],"warnings":[],"net":None}
    try:
        exit_price = require_number(closed.get("actual_exit_price"), "actual_exit_price", minimum=0, maximum=1)
        exit_fee = require_number(closed.get("exit_fee_dollars"), "exit_fee_dollars", minimum=0)
        expected = calculate_close(opened,exit_price,exit_fee)
        issues.extend(expected["issues"]); warnings.extend(expected["warnings"])
        for key in ("quantity_contracts","actual_entry_price","entry_fee_dollars"):
            if key in closed:
                source,copy = parse_decimal(opened.get(key)),parse_decimal(closed.get(key))
                if (source is None)!=(copy is None) or (source is not None and not near(source,copy)):
                    issues.append("SOURCE_OPEN_MISMATCH_"+key.upper())
        for key in ("ticker","side"):
            if key in closed and closed[key] != opened.get(key):
                issues.append("SOURCE_OPEN_IDENTITY_MISMATCH")
        q = parse_decimal(opened.get("quantity_contracts"))
        if closed.get("exit_notional_dollars") is not None:
            n = parse_decimal(closed["exit_notional_dollars"])
            if q is None or n is None or not near(n,q*exit_price):issues.append("CONTRADICTORY_EXIT_NOTIONAL")
        for key,expected_key in (("gross_pnl_dollars","gross"),("net_pnl_dollars","net")):
            value = parse_decimal(closed.get(key)); target = expected[expected_key]
            if value is None:issues.append("MISSING_OR_INVALID_"+key.upper())
            elif target is None or not near(value,target):issues.append("CONTRADICTORY_"+key.upper())
        if expected["net"] is not None:
            for key,flag in (("win",expected["net"]>0),("scratch",expected["net"]==0)):
                if closed.get(key) is not None and (type(closed[key]) is not bool or closed[key] is not flag):issues.append("CONTRADICTORY_"+key.upper())
        if closed.get("net_roi") is not None:
            value = parse_decimal(closed["net_roi"])
            if expected["roi"] is None or value is None or not near(value,expected["roi"]):issues.append("CONTRADICTORY_NET_ROI")
        elif expected["roi"] is not None:warnings.append("NET_ROI_NOT_RECORDED")
    except (AccountingEvidenceError, DecimalException) as error:
        issues.append(str(error) if isinstance(error,AccountingEvidenceError) else "UNSUPPORTED_FINANCIAL_RANGE")
    return {"version":VERSION,"status":"INSUFFICIENT_EVIDENCE" if issues else "RECONCILED","issues":sorted(set(issues)),"warnings":sorted(set(warnings)),"net":None if issues else parse_decimal(closed.get("net_pnl_dollars"))}
