"""Synthetic-only provider admission and request-budget prototype.

No network transports, production startup, or trading capabilities.
"""
from dataclasses import dataclass
from typing import Callable, Any


class AdmissionRefused(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderAdmission:
    provider: str
    scope: str
    rights_approved: bool
    budget_approved: bool
    max_requests: int


class SyntheticCollector:
    def __init__(self, admission: ProviderAdmission):
        if (
            not isinstance(admission, ProviderAdmission)
            or not isinstance(admission.provider, str)
            or not admission.provider.strip()
            or admission.scope != "SYNTHETIC_ONLY"
            or type(admission.rights_approved) is not bool
            or type(admission.budget_approved) is not bool
            or not admission.rights_approved
            or not admission.budget_approved
            or type(admission.max_requests) is not int
            or admission.max_requests < 1
        ):
            raise AdmissionRefused("Synthetic provider admission refused")
        self.admission = admission
        self.attempted = 0
        self.closed = False

    def collect(self, provider: str, fixture: Callable[[], Any]) -> Any:
        if self.closed:
            raise AdmissionRefused("Collector closed")
        if provider != self.admission.provider:
            raise AdmissionRefused("Provider not admitted")
        if self.attempted >= self.admission.max_requests:
            raise AdmissionRefused("Request budget exhausted")
        if not callable(fixture):
            raise AdmissionRefused("Synthetic fixture required")
        self.attempted += 1
        return fixture()

    def execute(self, capability: str) -> None:
        raise AdmissionRefused("Capability unavailable: " + str(capability))

    def stop(self) -> None:
        self.closed = True