"""Pure shutdown intents; not executions, fills, approvals, or journal mutations."""
import hashlib
import json
from decimal import Decimal


def plan_shutdown(session_id, positions, quotes, *, now, max_age):
    if not isinstance(session_id, str) or not session_id or type(now) is not int or type(max_age) is not int or max_age <= 0:
        raise ValueError("Explicit session and bounded clock policy required")
    intents, unresolved, seen = [], [], set()
    for position in positions:
        ident = position["trade_id"]
        if type(ident) is not str or not ident or ident in seen:
            raise ValueError("Duplicate or missing position identity")
        seen.add(ident)
        quote = quotes.get(position["symbol"])
        try:
            if not quote or quote.get("verified") is not True or not quote.get("source_id"):
                raise ValueError("MISSING_OR_UNVERIFIED_QUOTE")
            stamp = quote.get("observed_at")
            if type(stamp) is not int or not 0 <= now - stamp <= max_age:
                raise ValueError("STALE_OR_FUTURE_QUOTE")
            price = Decimal(str(quote["price"]))
            if not price.is_finite() or price <= 0:
                raise ValueError("INVALID_PRICE")
        except (ValueError, KeyError, ArithmeticError) as error:
            unresolved.append({"trade_id": ident, "reason": str(error)})
            continue
        key = hashlib.sha256(json.dumps([session_id, ident, "DAILY_SHUTDOWN"], separators=(",", ":")).encode()).hexdigest()
        intents.append({"idempotency_key": key, "trade_id": ident, "reason": "DAILY_SHUTDOWN",
                        "reference_price": str(price), "source_id": quote["source_id"],
                        "observed_at": stamp, "status": "INTENT_ONLY_NO_FILL"})
    return {"session_id": session_id, "entry_admission": "MUST_BE_QUIESCED_BY_CALLER",
            "intents": sorted(intents, key=lambda item: item["trade_id"]),
            "unresolved": sorted(unresolved, key=lambda item: item["trade_id"]),
            "executed_n": 0, "shutdown_complete": False}
