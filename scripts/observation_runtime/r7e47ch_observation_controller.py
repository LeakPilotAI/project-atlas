"""Offline-only Hyperliquid observation controller.

Consumes response bytes supplied by the caller.
Does not create network clients or start production services.
"""

from __future__ import annotations

from dataclasses import dataclass

from scripts.observation_runtime.r7e47aa_transport import parse_response


class ObservationControllerRefused(RuntimeError):
    pass


@dataclass(frozen=True)
class ObservationSnapshot:
    provider: str
    source: str
    market_count: int
    markets: tuple


class OfflineObservationController:
    def __init__(self) -> None:
        self._used = False

    def observe(self, response_bytes: bytes) -> ObservationSnapshot:
        if self._used:
            raise ObservationControllerRefused(
                "Controller already consumed its one observation"
            )

        if type(response_bytes) is not bytes:
            raise ObservationControllerRefused(
                "Response must be caller-supplied bytes"
            )

        self._used = True

        parsed = parse_response(response_bytes)

        if not isinstance(parsed, (list, tuple)):
            raise ObservationControllerRefused(
                "Unexpected parsed response type"
            )

        return ObservationSnapshot(
            provider="hyperliquid",
            source="CALLER_SUPPLIED_OFFLINE",
            market_count=len(parsed),
            markets=tuple(parsed),
        )

    def observe_live(self):
        raise ObservationControllerRefused(
            "Live provider requests are not available"
        )
