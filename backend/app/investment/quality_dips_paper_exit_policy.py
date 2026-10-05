"""Prospective terminal policy for QUALITY_DIPS_PAPER_V1.

This freezes exit *reasons*, not profit targets. Quality Dips is a long-horizon
research strategy: price decline alone never breaks the thesis and Atlas must not
retrofit favorable exits. Automatic PAPER closure may only be considered from a
new point-in-time V3 observation carrying an explicit terminal condition.
"""
from __future__ import annotations

from typing import Any, Dict

EXIT_POLICY_VERSION = "quality-dips-paper-exit-v1-thesis-integrity"
TERMINAL_STATES = frozenset({"THESIS_BROKEN"})
TERMINAL_BLOCKER_PHRASES = (
    "thesis integrity failed",
    "value-trap/falling-knife gate active",
)


def evaluate_exit(observation: Dict[str, Any]) -> Dict[str, Any]:
    prediction = dict(observation.get("prediction") or {})
    state = str(
        observation.get("classification")
        or prediction.get("patient_state")
        or ""
    ).upper().strip()
    blockers = [str(x or "").lower().strip() for x in (prediction.get("blockers") or [])]
    reason = None
    if state in TERMINAL_STATES:
        reason = "THESIS_BROKEN"
    elif any(phrase in blocker for blocker in blockers for phrase in TERMINAL_BLOCKER_PHRASES):
        reason = "THESIS_INTEGRITY_TERMINAL"

    return {
        "exit_policy_version": EXIT_POLICY_VERSION,
        "terminal": reason is not None,
        "terminal_reason": reason,
        "price_only_exit_allowed": False,
        "profit_target_exit": False,
        "stop_loss_exit": False,
        "automatic_real_money_execution": False,
        "execution": "PAPER_ONLY",
    }
