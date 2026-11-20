"""R7E47Y: offline-first Hyperliquid observation boundary.

No network transport, credentials, trading, or production startup.
Provider authorization and wire-level budget are not yet established.
"""

from dataclasses import dataclass

ENDPOINT = "https://api.hyperliquid.xyz/info"
ALLOWED_TYPE = "metaAndAssetCtxs"


class LiveBoundaryRefused(RuntimeError):
    pass


@dataclass(frozen=True)
class ObservationPlan:
    provider: str = "hyperliquid"
    endpoint: str = ENDPOINT
    request_type: str = ALLOWED_TYPE
    max_requests: int = 1
    rights_approved: bool = False
    budget_approved: bool = False


def validate(plan: ObservationPlan) -> dict:
    if type(plan) is not ObservationPlan:
        raise LiveBoundaryRefused("Invalid plan")

    if (
        plan.provider != "hyperliquid"
        or plan.endpoint != ENDPOINT
        or plan.request_type != ALLOWED_TYPE
        or type(plan.max_requests) is not int
        or plan.max_requests != 1
    ):
        raise LiveBoundaryRefused("Request outside allowlist")

    return {
        "provider": plan.provider,
        "endpoint": plan.endpoint,
        "body": {"type": plan.request_type},
        "max_requests": plan.max_requests,
        "network_enabled": False,
        "rights_verified": False,
        "budget_verified": False,
        "execution": "REFUSED",
    }


def execute(plan: ObservationPlan):
    validate(plan)
    raise LiveBoundaryRefused(
        "Network execution disabled until independent "
        "provider authorization and wire-budget enforcement"
    )
