"""Offline AFI holdout/intake preflight; no external authentication or skill claim."""
from __future__ import annotations

import re

from app.backtest.forecast_baselines import fingerprint
from app.backtest.forecast_chronology_audit import _clock, audit_declared_chronology
from app.backtest.forecast_evaluation import ForecastEvidenceRefused, _time
from app.backtest.forecast_evidence_state_report import build_evidence_state_report
from app.backtest.forecast_report import ForecastHistory

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_INTAKE_FIELDS = frozenset({
    "schema", "provider_id", "instrument_id", "asset_class", "source_id", "license_id",
    "license_digest", "permitted_uses", "observed_at", "published_at", "witnessed_at",
    "witness_identity", "witness_payload_digest", "receipt_id", "payload_digest",
    "revision_id", "previous_revision_id", "correction_published_at", "retention_policy",
    "source_complete", "verification_status",
})


def validate_intake_declaration(packet):
    """Validate a proposed intake envelope; a supplied witness claim is not proof."""
    if type(packet) is not dict or set(packet) != _INTAKE_FIELDS:
        raise ForecastEvidenceRefused("Complete exact evidence-intake declaration required")
    if packet["schema"] != "AFI_WITNESSED_SOURCE_INTAKE_V1":
        raise ForecastEvidenceRefused("Unsupported evidence-intake contract")
    for key in ("provider_id", "instrument_id", "asset_class", "source_id", "license_id",
                "witness_identity", "receipt_id", "revision_id", "retention_policy"):
        value = packet[key]
        if type(value) is not str or not value or len(value) > 256:
            raise ForecastEvidenceRefused("Missing or malformed intake identity")
    for key in ("license_digest", "witness_payload_digest", "payload_digest"):
        value = packet[key]
        if type(value) is not str or _DIGEST.fullmatch(value) is None:
            raise ForecastEvidenceRefused("Missing or malformed intake digest")
    if packet["permitted_uses"] != ["OFFLINE_RESEARCH"] or packet["verification_status"] != "DECLARED_UNVERIFIED":
        raise ForecastEvidenceRefused("Intake rights or verification claim is unsupported")
    if packet["source_complete"] is not True:
        raise ForecastEvidenceRefused("Complete source coverage declaration required")
    previous = packet["previous_revision_id"]
    corrected = packet["correction_published_at"]
    if (previous is None) != (corrected is None):
        raise ForecastEvidenceRefused("Incomplete correction lineage")
    if previous is not None and (type(previous) is not str or not previous or previous == packet["revision_id"]):
        raise ForecastEvidenceRefused("Invalid previous revision identity")
    observed, published, witnessed = (_clock(packet[key]) for key in
                                      ("observed_at", "published_at", "witnessed_at"))
    if not observed <= published <= witnessed:
        raise ForecastEvidenceRefused("Intake observation/publication/witness clocks contradict")
    if corrected is not None and not published <= _clock(corrected) <= witnessed:
        raise ForecastEvidenceRefused("Correction publication chronology contradicts witness")
    return {"schema": "AFI_INTAKE_PREFLIGHT_V1", "packet_sha256": fingerprint(packet),
            "status": "PENDING_INDEPENDENT_AUTHENTICATION", "license_verified": False,
            "witness_verified": False, "source_completeness_verified": False,
            "authoritative_use_allowed": False, "production_approved": False}


def prepare_holdout_readiness(selection, holdout, *, frozen_at, evidence_asof,
                              proposed_minimum_samples=None):
    """Bind disjoint synthetic cases without evaluating an unwitnessed holdout."""
    if (not isinstance(selection, (list, tuple)) or not isinstance(holdout, (list, tuple))
            or not selection or not holdout or len(selection) + len(holdout) > 64
            or any(type(row) is not ForecastHistory for row in (*selection, *holdout))):
        raise ForecastEvidenceRefused("Bounded exact selection and holdout histories required")
    frozen, asof = _time(frozen_at), _time(evidence_asof)
    if frozen > asof:
        raise ForecastEvidenceRefused("Freeze occurs after evaluation")
    if proposed_minimum_samples is not None and (type(proposed_minimum_samples) is not int
                                                 or not 2 <= proposed_minimum_samples <= 10000):
        raise ForecastEvidenceRefused("Proposed sample minimum is invalid")
    entries = (*selection, *holdout)
    chronology = audit_declared_chronology(entries, evidence_asof=asof)
    report = build_evidence_state_report(entries, evidence_asof=asof)
    by_id = {case["forecast_sha256"]: case for case in report["cases"]}
    if len(by_id) != len(entries):
        raise ForecastEvidenceRefused("Repeated forecast identity")
    selected_ids = {case["forecast_sha256"] for case in
                    build_evidence_state_report(selection, evidence_asof=asof)["cases"]}
    cohorts, targets, frozen_cases = {}, set(), []
    for case in report["cases"]:
        cohort = case["cohort"]
        window = case["window"]
        key = (cohort["asset_class"], cohort["asset_id"], cohort["horizon"], cohort["source_id"])
        binding = (cohort["model"], cohort["model_version"],
                   cohort["model_configuration_sha256"], cohort["lookback"],
                   cohort["release_source_sha256"], cohort["forecast_dataset_id"])
        if key in cohorts and cohorts[key] != binding:
            raise ForecastEvidenceRefused("Model/version or source substitution within holdout cohort")
        cohorts[key] = binding
        target = (*key, window["target_at"])
        if target in targets:
            raise ForecastEvidenceRefused("Repeated target leaks independent sample membership")
        targets.add(target)
        issue = _clock(window["issued_at"])
        is_selection = case["forecast_sha256"] in selected_ids
        if is_selection:
            if (issue >= frozen or window["status"] != "COMPLETE"
                    or case["outcome_status"] != "RESOLVED"
                    or case["diagnostic_exclusion_reason"] is not None
                    or _clock(case["revision"]["outcome_reconciled_asof"]) >= frozen
                    or _clock(case["revision"]["source_available_at"]) >= frozen):
                raise ForecastEvidenceRefused("Selection label unavailable or incomplete before freeze")
        elif issue < frozen:
            raise ForecastEvidenceRefused("Holdout forecast predates freeze")
        frozen_cases.append({"forecast_sha256": case["forecast_sha256"],
                             "partition": "SELECTION" if is_selection else "HOLDOUT",
                             "cohort": cohort, "issued_at": window["issued_at"],
                             "target_at": window["target_at"], "window_status": window["status"],
                             "outcome_status": case["outcome_status"],
                             "exclusion_reason": case["diagnostic_exclusion_reason"]})
    base = {"schema": "AFI_OFFLINE_HOLDOUT_READINESS_V1", "frozen_at": frozen.isoformat(),
            "asof": asof.isoformat(), "cases": frozen_cases,
            "selection_n": len(selection), "holdout_n": len(holdout),
            "selection_partition_sha256": fingerprint(sorted(selected_ids)),
            "holdout_partition_sha256": fingerprint(sorted(set(by_id) - selected_ids)),
            "holdout_mature_n": sum(case["partition"] == "HOLDOUT"
                                      and case["window_status"] == "COMPLETE"
                                      and case["outcome_status"] == "RESOLVED"
                                      and case["exclusion_reason"] is None
                                      for case in frozen_cases),
            "proposed_minimum_samples": proposed_minimum_samples,
            "sample_minimum_approved": False, "chronology_sha256": fingerprint(chronology),
            "dataset_freeze_independently_witnessed": False,
            "holdout_independently_unseen": False, "source_rights_verified": False,
            "authoritative_scored_n": 0, "calibration_established": False,
            "production_approved": False}
    return {**base, "protocol_sha256": fingerprint(base)}
