
"""Adversarial checks for the Phase 2D.3 authority integration."""

from types import SimpleNamespace
import importlib

import pytest

from app.backtest.historical_evidence_contract import HistoricalEvidenceResult


@pytest.mark.parametrize("mode", ["path", "bytes"])
@pytest.mark.parametrize(
    "authority_fields",
    [
        (True, False, True),
        (False, True, True),
        (False, False, False),
    ],
)
def test_contradictory_authority_fails_closed(
    monkeypatch, tmp_path, mode, authority_fields
):
    audit_module = importlib.import_module(
        "app.backtest.historical_availability_audit"
    )
    authority_module = importlib.import_module(
        "app.backtest.historical_authority_assessment"
    )

    evidence = HistoricalEvidenceResult(
        True,
        False,
        "STRUCTURALLY_CONSISTENT_UNAUTHENTICATED",
        (),
    )

    verified, authenticated, structurally_accepted = authority_fields

    monkeypatch.setattr(
        authority_module,
        "assess_historical_authority",
        lambda result: SimpleNamespace(
            authority_verified=verified,
            historical_availability_authenticated=authenticated,
            structurally_accepted=structurally_accepted,
        ),
    )

    manifest_payload = {
        "pit_aligned": True,
        "current_state_backfill_used": False,
    }

    if mode == "path":
        monkeypatch.setattr(
            audit_module, "load_manifest",
            lambda *args: manifest_payload,
        )
        monkeypatch.setattr(
            audit_module, "validate_historical_evidence",
            lambda *args, **kwargs: evidence,
        )

        result = audit_module.audit_historical_availability(
            tmp_path / "dataset.csv",
            tmp_path / "manifest.json",
            receipt=tmp_path / "receipt.json",
            expected_decision_at="2026-01-01T00:00:00Z",
        )
    else:
        manifest_module = importlib.import_module(
            "app.backtest.manifest"
        )
        evidence_module = importlib.import_module(
            "app.backtest.historical_evidence_contract"
        )

        monkeypatch.setattr(
            manifest_module, "load_manifest_bytes",
            lambda *args: manifest_payload,
        )
        monkeypatch.setattr(
            evidence_module, "validate_historical_evidence_bytes",
            lambda *args, **kwargs: evidence,
        )

        result = audit_module.audit_historical_availability_bytes(
            b"dataset",
            b"manifest",
            receipt_bytes=b"receipt",
            expected_decision_at="2026-01-01T00:00:00Z",
        )

    assert result.classification == "AUTHORITY_REFUSED"
    assert result.historical_availability_authenticated is False
    assert result.integrity_verified is False


@pytest.mark.parametrize("mode", ["path", "bytes"])
def test_normal_unauthenticated_authority_stays_unauthenticated(
    monkeypatch, tmp_path, mode
):
    audit_module = importlib.import_module(
        "app.backtest.historical_availability_audit"
    )

    evidence = HistoricalEvidenceResult(
        True,
        False,
        "STRUCTURALLY_CONSISTENT_UNAUTHENTICATED",
        (),
    )

    payload = {
        "pit_aligned": True,
        "current_state_backfill_used": False,
    }

    if mode == "path":
        monkeypatch.setattr(
            audit_module, "load_manifest",
            lambda *args: payload,
        )
        monkeypatch.setattr(
            audit_module, "validate_historical_evidence",
            lambda *args, **kwargs: evidence,
        )

        result = audit_module.audit_historical_availability(
            tmp_path / "dataset.csv",
            tmp_path / "manifest.json",
            receipt=tmp_path / "receipt.json",
            expected_decision_at="2026-01-01T00:00:00Z",
        )
    else:
        manifest_module = importlib.import_module(
            "app.backtest.manifest"
        )
        evidence_module = importlib.import_module(
            "app.backtest.historical_evidence_contract"
        )

        monkeypatch.setattr(
            manifest_module, "load_manifest_bytes",
            lambda *args: payload,
        )
        monkeypatch.setattr(
            evidence_module, "validate_historical_evidence_bytes",
            lambda *args, **kwargs: evidence,
        )

        result = audit_module.audit_historical_availability_bytes(
            b"dataset",
            b"manifest",
            receipt_bytes=b"receipt",
            expected_decision_at="2026-01-01T00:00:00Z",
        )

    assert result.classification == (
        "STRUCTURALLY_CONSISTENT_UNAUTHENTICATED"
    )
    assert result.historical_availability_authenticated is False
