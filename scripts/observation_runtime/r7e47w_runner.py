"""Bounded synthetic-only observation runner; no network or trading."""

from pathlib import Path

from scripts.observation_runtime.r7e47t_candidate import (
    AdmissionRefused,
    ProviderAdmission,
)
from scripts.observation_runtime.r7e47u_fixture_boundary import (
    FixtureBoundary,
    FixtureRefused,
)
from scripts.observation_runtime.r7e47v_budget_ledger import (
    BudgetRefused,
    DurableBudget,
)


class RunnerRefused(RuntimeError):
    pass


class SyntheticObservationRunner:
    def __init__(
        self,
        ledger_path: str | Path,
        admission: ProviderAdmission,
        *,
        enroll: bool = False,
    ):
        if (
            type(admission) is not ProviderAdmission
            or type(admission.provider) is not str
            or not admission.provider
            or admission.scope != "SYNTHETIC_ONLY"
            or admission.rights_approved is not True
            or admission.budget_approved is not True
            or type(admission.max_requests) is not int
            or not 1 <= admission.max_requests <= 10000
        ):
            raise RunnerRefused("Synthetic admission required")

        self.provider = admission.provider
        self.closed = False

        try:
            self.boundary = FixtureBoundary(
                admission.provider, admission.max_requests
            )
            self.ledger = DurableBudget(
                ledger_path,
                admission.provider,
                admission.max_requests,
                enroll=enroll,
            )
        except (FixtureRefused, BudgetRefused) as error:
            raise RunnerRefused("Runner initialization refused") from error

    def ingest(self, raw: bytes):
        if self.closed:
            raise RunnerRefused("Runner closed")

        if type(raw) is not bytes:
            raise RunnerRefused("Data-only bytes required")

        try:
            self.ledger.consume()
        except BudgetRefused as error:
            raise RunnerRefused("Durable synthetic budget refused") from error

        return self.boundary.ingest(raw)

    def remaining(self) -> int:
        if self.closed:
            raise RunnerRefused("Runner closed")
        try:
            return self.ledger.remaining()
        except BudgetRefused as error:
            raise RunnerRefused("Budget inspection refused") from error

    def stop(self) -> None:
        self.closed = True
        self.boundary.stop()

    def execute(self, capability: str) -> None:
        raise RunnerRefused("Capability unavailable")