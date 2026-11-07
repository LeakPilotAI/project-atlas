"""R7E47BI: strictly offline budgeted observation transport.

No HTTP implementation, URL opener, or arbitrary sender injection.
"""

from scripts.observation_runtime.r7e47y_live_boundary import (
    ObservationPlan,
    validate,
)
from scripts.observation_runtime.r7e47z_request_budget import RequestBudget
from scripts.observation_runtime.r7e47aa_transport import (
    TransportRefused,
    parse_response,
)


class OfflineFixtureTransport:
    def __init__(self, plan, budget, fixture):
        validate(plan)

        if type(plan) is not ObservationPlan:
            raise TransportRefused("Exact observation plan required")

        if type(budget) is not RequestBudget:
            raise TransportRefused("Exact durable budget required")

        if type(fixture) is not bytes:
            raise TransportRefused("Immutable fixture bytes required")

        self._budget = budget
        self._fixture = fixture
        self._attempted = False

    def execute(self):
        if self._attempted:
            raise TransportRefused("Transport already attempted")

        self._attempted = True
        self._budget.consume_before_attempt()
        return parse_response(self._fixture)

    def execute_live(self):
        raise TransportRefused("Network execution unavailable")
