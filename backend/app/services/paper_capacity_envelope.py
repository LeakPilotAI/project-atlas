"""Pure bounded-session capacity arithmetic; never grants operational admission."""


def assess_bounded_capacity(*, capacity, used, planned, shutdown_reserve):
    """Refuse an impossible declared envelope without touching a financial store.

    A passing arithmetic result is NOT an operational acceptance: actual workload,
    storage identities, independent review and guarded native load remain required.
    """
    values = (capacity, used, planned, shutdown_reserve)
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError("CAPACITY_ENVELOPE_NONNEGATIVE_INTEGERS_REQUIRED")
    if capacity == 0 or used > capacity or shutdown_reserve == 0:
        raise ValueError("CAPACITY_ENVELOPE_INVALID_BOUND")
    remaining = capacity - used
    required = planned + shutdown_reserve
    return {
        "schema": "ATLAS_BOUNDED_CAPACITY_ARITHMETIC_V1",
        "remaining": remaining,
        "required": required,
        "fits_declared_envelope": required <= remaining,
        "operational_admission": False,
        "native_load_verified": False,
    }


def assess_multi_store_envelope(stores):
    """Evaluate all declared stores; any exhausted store vetoes the envelope.

    This read-only calculation cannot replace a fresh native capacity read or
    independent operational admission. Unknown/missing stores fail closed.
    """
    required_names = frozenset({"GLOBAL", "QUALITY_DIPS", "HYPERLIQUID", "PERP_ORDERS", "REPORTS"})
    if type(stores) is not dict or set(stores) != required_names:
        raise ValueError("CAPACITY_ENVELOPE_COMPLETE_STORE_SET_REQUIRED")
    results = {}
    for name in sorted(required_names):
        row = stores[name]
        if type(row) is not dict or set(row) != {"capacity", "used", "planned", "shutdown_reserve"}:
            raise ValueError("CAPACITY_ENVELOPE_EXACT_STORE_FIELDS_REQUIRED")
        results[name] = assess_bounded_capacity(**row)
    return {
        "schema": "ATLAS_MULTI_STORE_CAPACITY_ARITHMETIC_V1",
        "stores": results,
        "fits_declared_envelope": all(row["fits_declared_envelope"] for row in results.values()),
        "operational_admission": False,
        "native_load_verified": False,
    }
