"""R7E47AA: isolated offline-first market-data transport.

No network requests are authorized by this module.
No Atlas backend, trading, WebSocket, or Discord imports.
"""

import json

from scripts.observation_runtime.r7e47y_live_boundary import (
    ObservationPlan,
    LiveBoundaryRefused,
    validate,
)
from scripts.observation_runtime.r7e47z_request_budget import (
    RequestBudget,
)

MAX_RESPONSE_BYTES = 2_000_000


class TransportRefused(RuntimeError):
    pass


def parse_response(raw):
    if type(raw) is not bytes:
        raise TransportRefused("Bytes required")

    if not raw or len(raw) > MAX_RESPONSE_BYTES:
        raise TransportRefused("Invalid response size")

    try:
        payload = json.loads(raw)
    except (UnicodeError, ValueError) as error:
        raise TransportRefused("Invalid JSON") from error

    if (
        not isinstance(payload, list)
        or len(payload) != 2
        or not isinstance(payload[0], dict)
        or not isinstance(payload[1], list)
    ):
        raise TransportRefused("Unexpected provider response")

    universe = payload[0].get("universe")

    if not isinstance(universe, list):
        raise TransportRefused("Missing universe")

    if len(universe) != len(payload[1]):
        raise TransportRefused("Asset context mismatch")

    return {
        "asset_count": len(universe),
        "valid_structure": True,
    }


class IsolatedTransport:
    def __init__(self, plan, budget):
        validate(plan)

        if type(plan) is not ObservationPlan:
            raise TransportRefused("Invalid plan")

        if type(budget) is not RequestBudget:
            raise TransportRefused("Durable budget required")

        self.plan = plan
        self.budget = budget

    def offline_status(self):
        return {
            "provider": "hyperliquid",
            "endpoint": self.plan.endpoint,
            "request_type": self.plan.request_type,
            "remaining_attempts": self.budget.remaining(),
            "network_enabled": False,
        }

    def execute(self):
        raise LiveBoundaryRefused(
            "Network disabled pending provider authorization "
            "and aggregate wire-budget verification"
        )
