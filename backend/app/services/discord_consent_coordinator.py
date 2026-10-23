"""Isolated E136 coordinator prototype; no production dispatch wiring."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from app.alerts.subscriptions import validate_discord_user_id
from app.services.discord_consent_generations import (
    ConsentStateError,
    DiscordConsentGenerations,
)
from app.services.discord_consent_witness import (
    ConsentWitnessError,
    DiscordConsentWitness,
)


class DiscordConsentCoordinator:
    """Fail-closed consent/witness coordination prototype.

    WARNING: Updates are not yet atomic across both SQLite databases.
    This class must not authorize production Discord delivery.
    """

    def __init__(self, consent_path: Path, witness_path: Path) -> None:
        self.consent = DiscordConsentGenerations(consent_path)
        self.witness = DiscordConsentWitness(witness_path)

    @classmethod
    def create(
        cls,
        consent_path: Path,
        witness_path: Path,
    ) -> DiscordConsentCoordinator:
        consent_path = Path(consent_path)
        witness_path = Path(witness_path)

        if consent_path.resolve() == witness_path.resolve():
            raise ConsentStateError("consent and witness paths must differ")

        if consent_path.exists() or witness_path.exists():
            raise ConsentStateError("coordinator databases already exist")

        DiscordConsentGenerations.create(consent_path)
        DiscordConsentWitness.create(witness_path)
        return cls(consent_path, witness_path)

    def _state(self, recipient_id: int) -> tuple[int, bool] | None:
        recipient = str(validate_discord_user_id(recipient_id))

        with closing(self.consent._connect()) as db:
            self.consent._assert_identity(db)
            row = db.execute(
                "SELECT generation, subscribed "
                "FROM consent_generations WHERE recipient_id=?",
                (recipient,),
            ).fetchone()

        if row is None:
            return None

        generation = row["generation"]
        subscribed = row["subscribed"]

        if type(generation) is not int or generation < 1:
            raise ConsentStateError("invalid consent generation")
        if subscribed not in (0, 1):
            raise ConsentStateError("invalid consent status")

        return generation, bool(subscribed)

    def set_subscription(self, recipient_id: int, subscribed: bool) -> int:
        recipient = str(validate_discord_user_id(recipient_id))
        if type(subscribed) is not bool:
            raise ValueError("subscribed must be boolean")

        # SQLite BEGIN IMMEDIATE serializes coordinator writers
        # across processes sharing this consent database.
        with closing(self.consent._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                self.consent._assert_identity(db)
                row = db.execute(
                    "SELECT generation, subscribed "
                    "FROM consent_generations WHERE recipient_id=?",
                    (recipient,),
                ).fetchone()

                current = None
                if row is not None:
                    generation = row["generation"]
                    status = row["subscribed"]

                    if type(generation) is not int or not 1 <= generation < (1 << 63):
                        raise ConsentStateError("invalid consent generation")
                    if status not in (0, 1):
                        raise ConsentStateError("invalid consent status")

                    current = (generation, bool(status))

                database_id = self.consent._database_id

                if current is not None:
                    previous_generation, previous_status = current

                    if not self.witness.matches(
                        recipient_id,
                        database_id,
                        previous_generation,
                        previous_status,
                    ):
                        raise ConsentWitnessError(
                            "consent and witness disagree; recovery required"
                        )

                    if previous_status == subscribed:
                        db.commit()
                        return previous_generation

                    if previous_generation >= (1 << 63) - 1:
                        raise ConsentStateError("consent generation exhausted")

                    next_generation = previous_generation + 1
                else:
                    next_generation = 1

                # Witness-first commit while holding the consent lock.
                # A crash between commits remains fail-closed and
                # requires explicit recovery.
                self.witness.observe(
                    recipient_id,
                    database_id,
                    next_generation,
                    subscribed,
                )

                if current is None:
                    db.execute(
                        "INSERT INTO consent_generations "
                        "(recipient_id, generation, subscribed) "
                        "VALUES (?, ?, ?)",
                        (recipient, next_generation, int(subscribed)),
                    )
                else:
                    db.execute(
                        "UPDATE consent_generations "
                        "SET generation=?, subscribed=? WHERE recipient_id=?",
                        (next_generation, int(subscribed), recipient),
                    )

                db.commit()
                return next_generation
            except BaseException:
                db.rollback()
                raise

    def authorized(self, recipient_id: int, generation: int) -> bool:
        if type(generation) is not int or generation < 1:
            return False

        try:
            if not self.consent.authorized(recipient_id, generation):
                return False

            return self.witness.matches(
                recipient_id,
                self.consent.database_id,
                generation,
                True,
            )
        except (
            ConsentStateError,
            ConsentWitnessError,
            sqlite3.Error,
            OSError,
            ValueError,
        ):
            return False
