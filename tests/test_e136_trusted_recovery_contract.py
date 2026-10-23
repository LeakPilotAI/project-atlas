"""E136 D4C-2: isolated trusted recovery policy contracts.

These tests document policy only. They do not activate Discord dispatch.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryEvidence:
    consent_matches_witness: bool
    trusted_checkpoint_available: bool
    trusted_checkpoint_matches: bool
    fresh_explicit_consent: bool


def may_restore_delivery_authority(evidence: RecoveryEvidence) -> bool:
    """Prototype fail-closed decision; not production authorization."""
    return (
        evidence.consent_matches_witness
        and evidence.trusted_checkpoint_available
        and evidence.trusted_checkpoint_matches
        and evidence.fresh_explicit_consent
    )


def test_matching_local_ledgers_alone_are_insufficient():
    evidence = RecoveryEvidence(True, False, False, True)
    assert not may_restore_delivery_authority(evidence)


def test_missing_trusted_checkpoint_denies_recovery():
    evidence = RecoveryEvidence(True, False, False, False)
    assert not may_restore_delivery_authority(evidence)


def test_stale_or_mismatched_checkpoint_denies_recovery():
    evidence = RecoveryEvidence(True, True, False, True)
    assert not may_restore_delivery_authority(evidence)


def test_missing_fresh_consent_denies_recovery():
    evidence = RecoveryEvidence(True, True, True, False)
    assert not may_restore_delivery_authority(evidence)


def test_local_disagreement_denies_recovery():
    evidence = RecoveryEvidence(False, True, True, True)
    assert not may_restore_delivery_authority(evidence)


def test_all_trusted_recovery_prerequisites_allow_policy_decision():
    evidence = RecoveryEvidence(True, True, True, True)
    assert may_restore_delivery_authority(evidence)
