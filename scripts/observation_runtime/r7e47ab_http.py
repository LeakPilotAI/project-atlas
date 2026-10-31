"""R7E47AB: bounded HTTP attempt path, offline-tested only.

The production HTTP sender is intentionally unavailable.
No network authorization is granted by this module.
"""

import json
from typing import Callable

from scripts.observation_runtime.r7e47y_live_boundary import (
    ObservationPlan,
    validate,
)
from scripts.observation_runtime.r7e47z_request_budget import (
    RequestBudget,
)
from scripts.observation_runtime.r7e47aa_transport import (
    MAX_RESPONSE_BYTES,
    TransportRefused,
    parse_response,
)

TIMEOUT_SECONDS = 10


def bounded_attempt(plan, budget, sender: Callable):
    """Execute one charged attempt through an injected sender.

    Intended exclusively for offline fake-sender testing.
    """
    validate(plan)

    if type(plan) is not ObservationPlan:
        raise TransportRefused("Invalid plan")

    if type(budget) is not RequestBudget:
        raise TransportRefused("Durable budget required")

    if not callable(sender):
        raise TransportRefused("Sender required")

    # Persist the charge before invoking any sender.
    budget.consume_before_attempt()

    raw = sender(
        endpoint=plan.endpoint,
        body={"type": plan.request_type},
        timeout=TIMEOUT_SECONDS,
        max_bytes=MAX_RESPONSE_BYTES,
        follow_redirects=False,
        retries=0,
    )

    return parse_response(raw)


def live_sender(**kwargs):
    raise TransportRefused(
        "Live HTTP sender disabled pending provider authorization"
    )


def execute_live(plan, budget):
    raise TransportRefused(
        "Real network execution unavailable"
    )
