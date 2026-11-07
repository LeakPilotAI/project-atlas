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
