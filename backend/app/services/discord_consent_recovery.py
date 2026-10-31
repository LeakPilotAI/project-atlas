"""Read-only E136 recovery diagnostics; never grants delivery authority."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from enum import Enum

from app.services.discord_consent_coordinator import DiscordConsentCoordinator
from app.services.discord_consent_generations import ConsentStateError
from app.services.discord_consent_witness import ConsentWitnessError


class RecoveryStatus(str, Enum):
    CONSISTENT = "CONSISTENT"
    MISSING_CONSENT = "MISSING_CONSENT"
    QUARANTINE = "QUARANTINE"
    UNVERIFIABLE = "UNVERIFIABLE"


@dataclass(frozen=True)
class RecoveryAssessment:
    status: RecoveryStatus
    generation: int | None = None
    subscribed: bool | None = None


def assess_recovery(
    coordinator: DiscordConsentCoordinator,
    recipient_id: int,
) -> RecoveryAssessment:
    """Inspect local evidence without modifying it.

    CONSISTENT is diagnostic only, not authorization or rollback proof.
    """
    try:
        state = coordinator._state(recipient_id)
        if state is None:
            return RecoveryAssessment(RecoveryStatus.MISSING_CONSENT)

        generation, subscribed = state
        if type(generation) is not int or not 1 <= generation < (1 << 63):
            return RecoveryAssessment(RecoveryStatus.UNVERIFIABLE)

        matches = coordinator.witness.matches(
            recipient_id,
            coordinator.consent.database_id,
            generation,
            subscribed,
        )
        if not matches:
            return RecoveryAssessment(RecoveryStatus.QUARANTINE)

        return RecoveryAssessment(
            RecoveryStatus.CONSISTENT,
            generation=generation,
            subscribed=subscribed,
        )
    except (
        ConsentStateError,
        ConsentWitnessError,
        sqlite3.Error,
        OSError,
        ValueError,
        TypeError,
    ):
        return RecoveryAssessment(RecoveryStatus.UNVERIFIABLE)
