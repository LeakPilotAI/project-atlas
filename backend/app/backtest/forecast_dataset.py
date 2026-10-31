"""Bounded offline AFI price-dataset review. No provider, storage or authority side effects.

Hashes establish consistency with supplied bytes, not truth, licensing or archive
provenance. Only synthetic fixtures can receive technical acceptance here.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.backtest.forecast_evaluation import (
    Forecast,
    ForecastEvidenceRefused,
    Observation,
    Outcome,
    _asset,
    _bounded,
    _identity,
    _number,
    _time,
    score_forecasts,
    select_asof,
)
from app.investment.market_hours import CALENDAR_YEARS, session_bounds

MAX_BYTES = 5_000_000
MAX_RECORDS = 10000


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ForecastEvidenceRefused("Duplicate JSON field")
        result[key] = value
    return result


def _json(raw):
    if type(raw) is not bytes or len(raw) > MAX_BYTES:
        raise ForecastEvidenceRefused("Bounded exact dataset bytes required")
    try:
        return json.loads(raw, object_pairs_hook=_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))
    except (ValueError, UnicodeError, RecursionError) as error:
        raise ForecastEvidenceRefused("Malformed dataset JSON") from error


def _fields(value, names):
    if type(value) is not dict or set(value) != set(names.split()):
        raise ForecastEvidenceRefused("Missing or unexpected dataset fields")


def _date(value):
    if type(value) is not str:
        raise ForecastEvidenceRefused("Explicit ISO time required")
    try:
        return _time(datetime.fromisoformat(value))
    except (ValueError, OverflowError) as error:
        raise ForecastEvidenceRefused("Invalid dataset time") from error


def _rows(value, limit=MAX_RECORDS):
    if type(value) is not list or len(value) > limit:
        raise ForecastEvidenceRefused("Bounded dataset rows required")
    return value


def _hash(value):
    if type(value) is not str or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ForecastEvidenceRefused("Exact SHA-256 required")


def _close(day, asset):
    if asset["asset_class"] == "CRYPTO":
        return datetime.combine(day, time(0), UTC)
    if day.year not in CALENDAR_YEARS:
        raise ForecastEvidenceRefused("Unsupported equity calendar year")
    bounds = session_bounds(datetime.combine(day, time(12), ZoneInfo("America/New_York")))
    return bounds[1] if bounds else None


def _future_closes(issued, asset):
    """Search only the accepted calendar; do not reject a known target because
    an unused tail of the search window extends into an unsupported year.
    Unknown required targets still refuse at their calling boundary.
    """
    end=issued+timedelta(days=15)
    if asset['asset_class']!='CRYPTO':
        supported_end=datetime.combine(date(max(CALENDAR_YEARS),12,31),time.max,ZoneInfo(asset['timezone']))
        end=min(end,supported_end)
    return [close for close in _grid(issued,end,asset) if close>issued]


def _grid(start, end, asset):
    zone = ZoneInfo(asset["timezone"])
    first, last = start.astimezone(zone).date(), end.astimezone(zone).date()
    if (last - first).days > 3660 or last < first:
        raise ForecastEvidenceRefused("Unsupported dataset period")
    result = []
    for offset in range((last - first).days + 1):
        close = _close(first + timedelta(days=offset), asset)
        if close is not None and start <= close <= end:
            result.append(close)
    return result


@dataclass(frozen=True)
class DatasetReview:
    status: str
    reasons: tuple[str, ...]
    manifest_sha256: str
    content_sha256: str
    manifest_bytes: bytes
    payload_bytes: bytes
    observations: tuple[Observation, ...]
    expected_n: int
    missing_n: int
    independently_authenticated: bool = False
    production_approved: bool = False


def _review_dataset(manifest_bytes, payload_bytes, *, asof):
    """Reject malformed/leaking inputs; return explicit quality/permission refusal states.

    DAILY_CLOSE only. Price returns exclude dividends. Split crossing forecasts
    are refused separately until economic-unit reconciliation is accepted.
    """
    asof = _time(asof)
    manifest, payload = _json(manifest_bytes), _json(payload_bytes)
    _fields(manifest, "schema dataset_id version evidence_class source acquired_at generated_at period_start period_end content_sha256 record_count assets quality revision_policy availability_basis universe_policy")
    _fields(payload, "schema records actions universe")
    if manifest["schema"] != "AFI_DATASET_MANIFEST_V1" or payload["schema"] != "AFI_PRICE_RECORDS_V1":
        raise ForecastEvidenceRefused("Unsupported dataset schema")
    for key in ("dataset_id", "version"):
        _identity(manifest[key])
    _hash(manifest["content_sha256"])
    digest = hashlib.sha256(payload_bytes).hexdigest()
    if digest != manifest["content_sha256"]:
        raise ForecastEvidenceRefused("Dataset content hash mismatch")
    if (manifest["revision_policy"] != "AS_PUBLISHED_APPEND_ONLY"
            or manifest["availability_basis"] != "AS_PUBLISHED_ARCHIVE"
            or manifest["universe_policy"] != "POINT_IN_TIME_WITH_DELISTED"):
        raise ForecastEvidenceRefused("PIT revisions, availability and universe coverage required")
    source = manifest["source"]
    _fields(source, "id provider license_id license_sha256 permission_status permissions")
    for key in ("id", "provider", "license_id"):
        _identity(source[key])
    _hash(source["license_sha256"])
    if source["permissions"] != ["OFFLINE_RESEARCH"]:
        raise ForecastEvidenceRefused("Explicit offline-only permission scope required")
    synthetic = manifest["evidence_class"] == "SYNTHETIC"
    if synthetic:
        if (source["provider"] != "SYNTHETIC" or source["license_id"] != "SYNTHETIC_FIXTURE"
                or source["permission_status"] != "SYNTHETIC_ONLY"):
            raise ForecastEvidenceRefused("Synthetic provenance mismatch")
    elif manifest["evidence_class"] != "HISTORICAL" or source["permission_status"] not in ("DECLARED", "UNKNOWN", "DENIED"):
        raise ForecastEvidenceRefused("Unsupported historical permission declaration")
    acquired, generated = _date(manifest["acquired_at"]), _date(manifest["generated_at"])
    start, end = _date(manifest["period_start"]), _date(manifest["period_end"])
    if not start <= end <= acquired <= generated <= asof:
        raise ForecastEvidenceRefused("Contradictory acquisition or observation window")
    assets = {}
    for asset in _rows(manifest["assets"], 64):
        _fields(asset, "asset_id asset_class currency timezone calendar granularity price_policy dividend_policy freshness_seconds")
        _asset(asset["asset_id"], asset["asset_class"])
        _identity(asset["currency"])
        crypto = asset["asset_class"] == "CRYPTO"
        if (asset["asset_id"] in assets or asset["granularity"] != "DAILY_CLOSE"
                or asset["timezone"] != ("UTC" if crypto else "America/New_York")
                or asset["calendar"] != ("CRYPTO_24_7" if crypto else "ATLAS_US_CASH_2026_2028")
                or asset["price_policy"] not in ("UNADJUSTED", "SPLIT_ADJUSTED")
                or asset["dividend_policy"] != "EXCLUDED_FROM_PRICE_RETURN"
                or type(asset["freshness_seconds"]) is not int or not 1 <= asset["freshness_seconds"] <= 604800):
            raise ForecastEvidenceRefused("Unsupported or conflicting asset/session convention")
        assets[asset["asset_id"]] = asset
    if not assets:
        raise ForecastEvidenceRefused("Explicit asset universe required")
    universe = {}
    for row in _rows(payload["universe"], 64):
        _fields(row, "asset_id listed_at listing_available_at delisted_at delisting_available_at")
        asset_id = row["asset_id"]
        if asset_id not in assets or asset_id in universe:
            raise ForecastEvidenceRefused("Conflicting universe identity")
        listed, known = _date(row["listed_at"]), _date(row["listing_available_at"])
        delisted = _date(row["delisted_at"]) if row["delisted_at"] is not None else None
        delist_known = _date(row["delisting_available_at"]) if row["delisting_available_at"] is not None else None
        if (known > acquired or (delisted is None) != (delist_known is None)
                or (delisted is not None and (delisted <= listed or delist_known > acquired))):
            raise ForecastEvidenceRefused("Invalid universe chronology")
        universe[asset_id] = (listed, known, delisted, delist_known)
    if set(universe) != set(assets):
        raise ForecastEvidenceRefused("Incomplete point-in-time universe")
    actions, action_ids = [], set()
    for row in _rows(payload["actions"]):
        fields = "action_id asset_id kind effective_at available_at amount"
        provenance_fields = {"economic_unit", "source_id", "source_sha256"}
        if type(row) is dict and provenance_fields.intersection(row):
            _fields(row, fields+" economic_unit source_id source_sha256")
            _identity(row["source_id"])
            _hash(row["source_sha256"])
        else:
            _fields(row, fields)
        _identity(row["action_id"])
        if (row["action_id"] in action_ids or row["asset_id"] not in assets
                or assets[row["asset_id"]]["asset_class"] == "CRYPTO"
                or row["kind"] not in ("SPLIT", "DIVIDEND")):
            raise ForecastEvidenceRefused("Unsupported or duplicate corporate action")
        asset = assets[row["asset_id"]]
        expected_unit = ("NEW_SHARES_PER_OLD_SHARE" if row["kind"] == "SPLIT"
                         else asset["currency"]+"_PER_SHARE")
        if provenance_fields.intersection(row) and row["economic_unit"] != expected_unit:
            raise ForecastEvidenceRefused("Corporate action economic unit mismatch")
        effective, available = _date(row["effective_at"]), _date(row["available_at"])
        if available > acquired:
            raise ForecastEvidenceRefused("Future action availability")
        listed, _, delisted, _ = universe[row["asset_id"]]
        if effective < listed or (delisted is not None and effective >= delisted):
            raise ForecastEvidenceRefused("Corporate action outside point-in-time asset membership")
        _number(row["amount"], positive=True)
        action_ids.add(row["action_id"])
        actions.append((row, effective, available))
    records = _rows(payload["records"])
    if type(manifest["record_count"]) is not int or manifest["record_count"] != len(records):
        raise ForecastEvidenceRefused("Dataset record count mismatch")
    observations, ids, revisions, timestamps = [], set(), set(), set()
    actual = {key: set() for key in assets}
    for row in records:
        fields = "record_id asset_id observed_at available_at raw_price value source_id revision applied_action_ids"
        if type(row) is dict and "source_sha256" in row:
            _fields(row, fields+" source_sha256")
            _hash(row["source_sha256"])
        else:
            _fields(row, fields)
        for key in ("record_id", "source_id", "revision"):
            _identity(row[key])
        asset_id = row["asset_id"]
        if asset_id not in assets or row["source_id"] != source["id"] or row["record_id"] in ids:
            raise ForecastEvidenceRefused("Repeated or conflicting observation identity")
        asset = assets[asset_id]
        observed, available = _date(row["observed_at"]), _date(row["available_at"])
        listed, _, delisted, _ = universe[asset_id]
        if (not start <= observed <= end or not observed <= available <= acquired
                or observed < listed or (delisted is not None and observed >= delisted)
                or observed != _close(observed.astimezone(ZoneInfo(asset["timezone"])).date(), asset)):
            raise ForecastEvidenceRefused("Invalid session, availability or membership")
        revision = (asset_id, observed, row["revision"])
        stamp = (asset_id, observed, available)
        if revision in revisions or stamp in timestamps:
            raise ForecastEvidenceRefused("Reused or conflicting source revision")
        ids.add(row["record_id"])
        revisions.add(revision)
        timestamps.add(stamp)
        raw, value = _number(row["raw_price"], positive=True), _number(row["value"], positive=True)
        if "source_sha256" in row:
            identity_payload = {'asset_id': row["asset_id"], 'observed_at': row["observed_at"],
                                'received_at': row["available_at"], 'value': row["value"],
                                'source_sha256': row["source_sha256"]}
            identity_bytes = (json.dumps(identity_payload, sort_keys=True, separators=(",", ":"),
                                         allow_nan=False)+"\n").encode()
            expected_revision = hashlib.sha256(identity_bytes).hexdigest()
            if row["record_id"] != expected_revision or row["revision"] != expected_revision:
                raise ForecastEvidenceRefused("Observation source/receipt revision binding mismatch")
        applicable = [(a, e, k) for a, e, k in actions if a["asset_id"] == asset_id
                      and a["kind"] == "SPLIT" and observed < e <= available and k <= available]
        expected_ids = sorted(a["action_id"] for a, _, _ in applicable) if asset["price_policy"] == "SPLIT_ADJUSTED" else []
        if type(row["applied_action_ids"]) is not list or row["applied_action_ids"] != expected_ids:
            raise ForecastEvidenceRefused("Future, missing or duplicate split adjustment")
        expected = raw
        for a, _, _ in applicable if expected_ids else []:
            expected /= a["amount"]
        if not math.isclose(value, expected, rel_tol=1e-12, abs_tol=0):
            raise ForecastEvidenceRefused("Incorrect split adjustment or undeclared price transformation")
        actual[asset_id].add(observed)
        observations.append(Observation(row["record_id"], asset_id, asset["asset_class"], observed, available,
                                        value, row["source_id"], row["revision"]))
    quality = manifest["quality"]
    _fields(quality, "max_missing_fraction min_history_per_asset")
    fraction = _number(quality["max_missing_fraction"])
    minimum = quality["min_history_per_asset"]
    if not 0 <= fraction <= .2 or type(minimum) is not int or not 2 <= minimum <= MAX_RECORDS:
        raise ForecastEvidenceRefused("Unsupported quality requirements")
    expected_n, missing_n, sparse = 0, 0, False
    for asset_id, asset in assets.items():
        listed, _, delisted, _ = universe[asset_id]
        expected = {t for t in _grid(start, end, asset) if t >= listed and (delisted is None or t < delisted)}
        if expected_n + len(expected) > MAX_RECORDS:
            raise ForecastEvidenceRefused("Expected observation grid exceeds bound")
        missing = len(expected - actual[asset_id])
        expected_n += len(expected)
        missing_n += missing
        sparse |= len(actual[asset_id]) < minimum or not expected or missing / len(expected) > fraction
    reasons = []
    if not synthetic:
        reasons.append("PROVIDER_RIGHTS_AND_ARCHIVE_PROVENANCE_NOT_INDEPENDENTLY_VERIFIED")
        if source["permission_status"] == "DENIED":
            reasons.append("PROVIDER_PERMISSION_DENIED")
    if sparse:
        reasons.append("INSUFFICIENT_HISTORY_OR_COMPLETENESS")
    status = "BLOCKED_AUTHORIZATION" if not synthetic else "INSUFFICIENT_EVIDENCE" if sparse else "ACCEPTED_SYNTHETIC"
    return DatasetReview(status, tuple(reasons), hashlib.sha256(manifest_bytes).hexdigest(), digest,
                         manifest_bytes, payload_bytes, tuple(observations), expected_n, missing_n)



def review_dataset(manifest_bytes, payload_bytes, *, asof):
    """Public malformed-input boundary; typed refusal never grants partial acceptance."""
    try:
        return _review_dataset(manifest_bytes, payload_bytes, asof=asof)
    except ForecastEvidenceRefused:
        raise
    except (TypeError, KeyError, ValueError, OverflowError, RecursionError) as error:
        raise ForecastEvidenceRefused("Malformed or unsupported dataset evidence") from error


def score_dataset_forecasts(review, forecasts, outcomes, *, asof, minimum_samples=20, outcome_asof=None):
    """Revalidate bytes before use; bind input, target and outcomes to reviewed fixtures.

    First daily close strictly after issuance defines 1D. Fifth defines 5D.
    Other horizons deliberately refuse pending explicit convention acceptance.
    """
    _bounded(forecasts, Forecast)
    _bounded(outcomes, Outcome)
    forecasts, outcomes = tuple(forecasts), tuple(outcomes)
    asof = _time(asof)
    outcome_asof = asof if outcome_asof is None else _time(outcome_asof)
    if outcome_asof > asof:
        raise ForecastEvidenceRefused("Outcome vintage exceeds dataset review time")
    if type(review) is not DatasetReview:
        raise ForecastEvidenceRefused("Reviewed dataset required")
    checked = review_dataset(review.manifest_bytes, review.payload_bytes, asof=asof)
    if review != checked or checked.status != "ACCEPTED_SYNTHETIC":
        raise ForecastEvidenceRefused("Unaccepted or substituted dataset review")
    manifest, payload = _json(review.manifest_bytes), _json(review.payload_bytes)
    assets = {a["asset_id"]: a for a in manifest["assets"]}
    universe = {u["asset_id"]: u for u in payload["universe"]}
    # Validate typed, bounded inputs before any iteration or identity lookup.
    report = score_forecasts(forecasts, outcomes, asof=outcome_asof, minimum_samples=minimum_samples)
    by_id = {f.forecast_id: f for f in forecasts}
    for forecast in forecasts:
        asset = assets.get(forecast.asset_id)
        if (asset is None or forecast.dataset_id != manifest["dataset_id"]
                or forecast.dataset_sha256 != review.content_sha256
                or forecast.dataset_manifest_sha256 != review.manifest_sha256
                or forecast.dataset_version != manifest["version"] or forecast.evidence_class != "SYNTHETIC"
                or forecast.horizon not in ("1D", "5D")):
            raise ForecastEvidenceRefused("Unbound dataset or unsupported target convention")
        issued = _time(forecast.issued_at)
        member = universe[forecast.asset_id]
        if (_date(member["listed_at"]) > issued or _date(member["listing_available_at"]) > issued
                or (member["delisted_at"] is not None and _date(member["delisted_at"]) <= issued)):
            raise ForecastEvidenceRefused("Asset unavailable in issue-time universe")
        selected = select_asof(review.observations, asset_id=forecast.asset_id, asset_class=forecast.asset_class,
                               cutoff=issued, max_age=timedelta(seconds=asset["freshness_seconds"]))
        row = selected["record"]
        if (row is None or row.value != forecast.reference_price or row.observed_at != forecast.input_observed_at
                or row.available_at != forecast.input_available_at):
            raise ForecastEvidenceRefused("Forecast input differs from latest available dataset observation")
        closes = _future_closes(issued,asset)
        index = 0 if forecast.horizon == "1D" else 4
        if len(closes) <= index or forecast.target_at != closes[index]:
            raise ForecastEvidenceRefused("Forecast target/session mismatch")
        if any(a["asset_id"] == forecast.asset_id and a["kind"] == "SPLIT"
               and row.observed_at < _date(a["effective_at"]) <= forecast.target_at for a in payload["actions"]):
            raise ForecastEvidenceRefused("Cross-split economic-unit reconciliation not accepted")
    for outcome in outcomes:
        forecast = by_id[outcome.forecast_id]
        candidates = [r for r in review.observations if r.asset_id == outcome.asset_id
                      and r.observed_at == outcome.target_at and r.available_at <= outcome_asof]
        if not candidates:
            raise ForecastEvidenceRefused("Outcome has no available dataset evidence")
        row = max(candidates, key=lambda r: r.available_at)
        if (row.value != outcome.price or row.source_id != outcome.source_id or row.revision != outcome.revision
                or row.available_at != outcome.available_at or outcome.asset_class != forecast.asset_class):
            raise ForecastEvidenceRefused("Outcome differs from available dataset revision")
    report["outcome_asof"] = outcome_asof.isoformat()
    report["dataset_review_asof"] = asof.isoformat()
    report["dataset_integrity_verified"] = True
    report["calendar_horizon_semantics"] = "EXPLICIT_DAILY_CLOSE_1D_5D_SYNTHETIC_ONLY"
    report["manifest_sha256"] = review.manifest_sha256
    return report
