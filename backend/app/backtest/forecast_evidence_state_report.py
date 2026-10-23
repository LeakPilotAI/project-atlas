"""Versioned, read-only companion to immutable V1 forecast accountability output."""
from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime
from html import escape

from app.backtest.forecast_artifacts import publish_research_text
from app.backtest.forecast_baselines import fingerprint
from app.backtest.forecast_dataset import _json
from app.backtest.forecast_evaluation import ForecastEvidenceRefused, _time
from app.backtest.forecast_observation_maturity import score_complete_synthetic_windows
from app.backtest.forecast_outcomes import _forecast, verify_outcome_history
from app.backtest.forecast_report import build_accountability_report, render_accountability_report


def _bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def build_evidence_state_report(entries, *, evidence_asof):
    """Recompute V1 and source-bound window states; never rewrite V1 artifacts."""
    base = build_accountability_report(entries, evidence_asof=evidence_asof)
    render_accountability_report(base)
    asof = _time(evidence_asof)
    cohorts = []
    for entry in entries:
        checked = verify_outcome_history(entry.forecast_path, entry.forecast_review,
                                         evidence_asof=asof, history=entry.history,
                                         expected_head=entry.expected_head,
                                         source_review=entry.source_review)
        original = _json(entry.forecast_review.manifest_bytes)
        review = entry.history[-1][1] if entry.history else entry.forecast_review
        latest = _json(review.manifest_bytes)
        if (latest["dataset_id"] != original["dataset_id"]
                or latest["source"]["id"] != original["source"]["id"]):
            raise ForecastEvidenceRefused("Outcome source or dataset substituted")
        forecast = _forecast(checked["forecast"])
        analysis = replace(forecast, dataset_sha256=review.content_sha256,
                           dataset_manifest_sha256=review.manifest_sha256,
                           dataset_version=latest["version"])
        observation = checked["records"][-1]["observation"] if checked["records"] else None
        outcome = []
        if observation is not None:
            from app.backtest.forecast_evaluation import Outcome

            outcome = [Outcome(forecast.forecast_id, forecast.asset_id, forecast.asset_class,
                               forecast.target_at, _time(forecast.target_at),
                               _time(datetime.fromisoformat(observation["available_at"])),
                               observation["value"], observation["source_id"],
                               observation["revision"], "SYNTHETIC")]
        strict = score_complete_synthetic_windows(review, [analysis], outcome, asof=asof)
        window = strict["window_evidence"][0]
        source_row = next(row for row in base["rows"]
                          if row["forecast_sha256"] == checked["forecast"]["forecast_sha256"])
        publication_order = "CONSISTENT_DECLARED_TIMES"
        for index, (record, item) in enumerate(zip(checked["records"], entry.history)):
            history_manifest = _json(item[1].manifest_bytes)
            if _time(datetime.fromisoformat(history_manifest["generated_at"])) > _time(
                datetime.fromisoformat(record["outcome_asof"])
            ):
                publication_order = "UNVERIFIED_REVIEW_POSTDATES_OUTCOME"
                break
            if (index and record["event"] == "CORRECTION"
                    and _time(datetime.fromisoformat(record["observation"]["available_at"]))
                    <= _time(datetime.fromisoformat(checked["records"][index - 1]["outcome_asof"]))):
                publication_order = "UNVERIFIED_BACKDATED_CORRECTION"
                break
        exclusion = ("PUBLICATION_ORDER_UNVERIFIED" if publication_order != "CONSISTENT_DECLARED_TIMES"
                     else "OBSERVATION_" + window["status"] if window["status"] != "COMPLETE"
                     else "NO_RECORDED_OUTCOME" if observation is None
                     else None)
        cohorts.append({"case_contract": "AFI_EVIDENCE_STATE_CASE_V2_1",
                        "cohort": {"asset_id": forecast.asset_id, "asset_class": forecast.asset_class,
                                   "horizon": forecast.horizon, "model": forecast.model_id,
                                   "model_version": forecast.model_version,
                                   "model_configuration_sha256": source_row.get("model_configuration_sha256"),
                                   "lookback": source_row["lookback"],
                                   "source_id": latest["source"]["id"],
                                   "forecast_dataset_id": source_row["forecast_dataset_id"],
                                   "forecast_dataset_version": source_row["forecast_dataset_version"],
                                   "forecast_dataset_sha256": entry.forecast_review.content_sha256,
                                   "forecast_manifest_sha256": entry.forecast_review.manifest_sha256,
                                   "outcome_dataset_sha256": review.content_sha256,
                                   "release_source_sha256": source_row["release_source_sha256"]},
                        "revision": {"latest_event": source_row["latest_event"],
                                     "source_revision": source_row["source_revision"],
                                     "source_available_at": source_row["source_available_at"],
                                     "outcome_reconciled_asof": source_row["last_reconciled_asof"],
                                     "input_source_revision": source_row.get("input_source_revision"),
                                     "correction_n": source_row["correction_n"],
                                     "history_n": source_row["history_n"]},
                        "diagnostic_exclusion_reason": exclusion,
                        "publication_order_status": publication_order,
                        "authoritative_exclusion_reason": "SYNTHETIC_UNAUTHENTICATED",
                        "forecast_sha256": checked["forecast"]["forecast_sha256"],
                        "forecast_artifact_sha256": checked["forecast"]["artifact_sha256"],
                        "outcome_head": entry.expected_head, "outcome_status": source_row["status"],
                        "window": window, "diagnostic_scored_n": (
                            strict["diagnostic"]["scored_n"] if exclusion is None else 0),
                        "authoritative_scored_n": 0})
    cohorts.sort(key=lambda row: row["forecast_sha256"])
    result = {"schema": "AFI_EVIDENCE_STATE_REPORT_V2", "source_report_sha256": base["report_sha256"],
              "source_report_bytes_sha256": hashlib.sha256(
                  (json.dumps(base, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
              ).hexdigest(),
              "asof": asof.isoformat(), "cases": cohorts,
              "legacy_report_unchanged": True, "authenticated_publication": False,
              "authoritative_scored_n": 0, "production_approved": False,
              "trading_authority": False}
    return {**result, "report_sha256": fingerprint(result)}


def render_evidence_state_report(report, entries, *, evidence_asof):
    """Scriptless companion view; independent V1 rendering stays byte-identical."""
    if report != build_evidence_state_report(entries, evidence_asof=evidence_asof):
        raise ForecastEvidenceRefused("Evidence-state report differs from source histories")
    cells = []
    for case in report["cases"]:
        window = case["window"]
        values = (window["asset_id"], window["horizon"], window["source_id"],
                  case["cohort"]["model_version"], window["issued_at"], window["target_at"],
                  window["status"], case["outcome_status"],
                  case["revision"]["latest_event"] or "—",
                  case["revision"]["source_revision"] or "—",
                  window["reason"] or "—", case["publication_order_status"],
                  case["diagnostic_exclusion_reason"] or "—",
                  str(window["available_n"]),
                  str(window["required_n"]), ", ".join(window["missing_at"]) or "—")
        cells.append("<tr>" + "".join("<td>" + escape(value) + "</td>" for value in values) + "</tr>")
    heads = ("Asset", "Horizon", "Source", "Model version", "Issued UTC", "Target UTC",
             "Evidence state", "Recorded outcome", "Latest revision event", "Source revision",
             "Reason", "Publication order", "Diagnostic exclusion", "Available", "Required", "Missing closes")
    return ("<!doctype html><html lang=\"en\"><meta charset=\"utf-8\"><title>Atlas evidence states</title>"
            "<main><h1>Forecast observation evidence states</h1>"
            "<p>Offline structural research only. No authenticated publication, authoritative performance, "
            "production or trading approval. Original V1 report remains unchanged.</p><table><thead><tr>"
            + "".join("<th scope=\"col\">" + escape(head) + "</th>" for head in heads)
            + "</tr></thead><tbody>" + "".join(cells) + "</tbody></table></main></html>")


def publish_evidence_state_report(root, entries, *, evidence_asof):
    """Explicit opt-in export; immutable files use existing checked publisher."""
    report = build_evidence_state_report(entries, evidence_asof=evidence_asof)
    raw = _bytes(report).decode()
    html = render_evidence_state_report(report, entries, evidence_asof=evidence_asof)
    json_path = publish_research_text(root, raw, extension=".json")
    html_path = publish_research_text(root, html, extension=".html")
    if json_path.read_text(encoding="utf-8") != raw or html_path.read_text(encoding="utf-8") != html:
        raise ForecastEvidenceRefused("Evidence-state export read-back failed")
    return {"schema": "AFI_EVIDENCE_STATE_EXPORT_V2", "report": json_path.name,
            "dashboard": html_path.name, "source_report_sha256": report["source_report_sha256"],
            "authoritative_scored_n": 0, "production_approved": False}
