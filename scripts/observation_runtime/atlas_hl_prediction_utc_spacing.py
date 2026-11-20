"""Hyperliquid public source-only forecast cadence, never a financial grant.

Wait to ACTUAL issued UTC separation, not a monotonic sleep assumption.
Independent peer-clock uncertainty is reserved across both observations.
This module does not connect, fetch, access credentials, sign, or start PAPER.
"""
from __future__ import annotations

import time

MIN_SPACING_MS = 10_000
SAFETY_MARGIN_MS = 250
MAX_WAIT_MS = 15_000
MAX_UNCERTAINTY_MS = 1_000
MIN_UNIX_MS = 1_700_000_000_000


def _exact_ms(value, label):
    if type(value) is not int or value < 0:
        raise ValueError("HL_UTC_SPACING_" + label + "_INVALID")
    return value


def next_forecast_utc_start(
    *, first_observed_ms, first_uncertainty_ms, sample_precise,
    verify_precise, sleep=time.sleep, monotonic=time.monotonic,
):
    """Return (start_ms, uncertainty_ms) only for an adequately separated sample.

    Call only in a NEW, separately consented public data-only collector.
    Functions return actual sample and same-process verification from the
    original selected operational NTP clock; do not substitute Windows time.
    Never invent or change provider nextFundingTime or any already-consumed
    original timestamp. Elapsed/dwell budget is 15 seconds, at most 5 samples.
    """
    if (type(first_observed_ms) is not int
            or first_observed_ms < MIN_UNIX_MS
            or type(first_uncertainty_ms) is not int
            or not 0 <= first_uncertainty_ms <= MAX_UNCERTAINTY_MS
            or not callable(sample_precise) or not callable(verify_precise)
            or not callable(sleep) or not callable(monotonic)):
        raise ValueError("HL_UTC_SPACING_ORIGINAL_EVIDENCE_REQUIRED")
    begun = monotonic()
    if type(begun) not in (int, float):
        raise ValueError("HL_UTC_SPACING_MONOTONIC_INVALID")
    previous_mono = begun
    previous_utc = None
    target = (first_observed_ms + MIN_SPACING_MS
              + first_uncertainty_ms + MAX_UNCERTAINTY_MS
              + SAFETY_MARGIN_MS)
    for _ in range(5):
        now = monotonic()
        if type(now) not in (int, float) or now < previous_mono:
            raise ValueError("HL_UTC_SPACING_MONOTONIC_ROLLBACK")
        previous_mono = now
        if now - begun > MAX_WAIT_MS / 1000:
            raise ValueError("HL_UTC_SPACING_WAIT_DEADLINE_REFUSED")
        sample = sample_precise()
        if (type(sample) is not dict or set(sample) != {
                "schema", "utc_ns", "monotonic_ns", "uncertainty_ms", "source"}
                or sample["schema"] != "ATLAS_INDEPENDENT_PRECISE_UTC_V1"
                or type(sample["utc_ns"]) is not int
                or type(sample["monotonic_ns"]) is not int
                or type(sample["uncertainty_ms"]) is not int
                or not 0 <= sample["uncertainty_ms"] <= MAX_UNCERTAINTY_MS
                or type(sample["source"]) is not str
                or not sample["source"].startswith("ATLAS_NTP_V1:")
                or verify_precise(sample) is not True):
            raise ValueError("HL_UTC_SPACING_ORIGINAL_NTP_PROOF_REFUSED")
        utc_ms = sample["utc_ns"] // 1_000_000
        if utc_ms < first_observed_ms or (
                previous_utc is not None and utc_ms < previous_utc):
            raise ValueError("HL_UTC_SPACING_UTC_ROLLBACK")
        previous_utc = utc_ms
        # The uncertainty of BOTH actual independent samples must fit
        # strictly inside the verified time separation.
        minimum = (MIN_SPACING_MS + first_uncertainty_ms
                   + sample["uncertainty_ms"])
        if utc_ms - first_observed_ms >= minimum + SAFETY_MARGIN_MS:
            return utc_ms, sample["uncertainty_ms"]
        to_wait_ms = max(target - utc_ms, minimum + SAFETY_MARGIN_MS
                         - (utc_ms - first_observed_ms), 0)
        if to_wait_ms <= 0 or to_wait_ms > MAX_WAIT_MS:
            raise ValueError("HL_UTC_SPACING_ESTIMATE_REFUSED")
        if now - begun + to_wait_ms / 1000 > MAX_WAIT_MS / 1000:
            raise ValueError("HL_UTC_SPACING_BUDGET_EXHAUSTED")
        sleep(to_wait_ms / 1000)
    raise ValueError("HL_UTC_SPACING_SAMPLES_EXHAUSTED")
