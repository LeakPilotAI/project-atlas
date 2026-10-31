"""R7E47AD: integrated offline collector.

Real network execution remains disabled.
"""

from scripts.observation_runtime.r7e47y_live_boundary import (
    ObservationPlan,
    LiveBoundaryRefused,
    validate,
)
from scripts.observation_runtime.r7e47z_request_budget import (
    RequestBudget,
)
from scripts.observation_runtime.r7e47ab_http import (
    bounded_attempt,
)
from scripts.observation_runtime.r7e47ac_sender import (
    describe_request,
)


class CollectorRefused(RuntimeError):
    pass


class SupervisedCollector:
    def __init__(self, plan, budget):
        validate(plan)

        if type(plan) is not ObservationPlan:
            raise CollectorRefused("Invalid observation plan")

        if type(budget) is not RequestBudget:
            raise CollectorRefused("Durable budget required")

        self.plan = plan
        self.budget = budget

    def describe(self):
        return {
            "request": describe_request(),
            "remaining_attempts": self.budget.remaining(),
            "network_enabled": False,
        }

    def run_offline(self, fake_sender):
        return bounded_attempt(
            self.plan,
            self.budget,
            fake_sender,
        )

    def run_live(self):
        raise LiveBoundaryRefused(
            "Live collection disabled until provider authorization "
            "and aggregate request controls are verified"
        )
