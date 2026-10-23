import copy
import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from app.backtest.forecast_dataset import review_dataset, score_dataset_forecasts
from app.backtest.forecast_evaluation import (
    Forecast,
    ForecastEvidenceRefused,
    Outcome,
    ReplayWindow,
    audit_selection_protocol,
    forecast_fingerprint,
    select_asof,
    walk_forward_plan,
)

A = "US_EQUITY:AAPL"
FRIDAY = "2026-10-16T20:00:00+00:00"
MONDAY = "2026-10-19T20:00:00+00:00"
ASOF = datetime(2026, 10, 20, tzinfo=UTC)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def fixture():
    asset = {'asset_id': A, 'asset_class': 'US_EQUITY', 'currency': 'USD', 'timezone': 'America/New_York', 'calendar': 'ATLAS_US_CASH_2026_2028', 'granularity': 'DAILY_CLOSE', 'price_policy': 'UNADJUSTED', 'dividend_policy': 'EXCLUDED_FROM_PRICE_RETURN', 'freshness_seconds': 345600}
    records = [{'record_id': f'r{i}', 'asset_id': A, 'observed_at': t, 'available_at': t, 'raw_price': p, 'value': p, 'source_id': 'fixture', 'revision': 'v1', 'applied_action_ids': []}
               for i, (t, p) in enumerate(((FRIDAY, 100), (MONDAY, 120)))]
    payload = {'schema': 'AFI_PRICE_RECORDS_V1', 'records': records, 'actions': [], 'universe': [{'asset_id': A, 'listed_at': '2026-01-01T00:00:00+00:00', 'listing_available_at': '2026-01-01T00:00:00+00:00', 'delisted_at': None, 'delisting_available_at': None}]}
    manifest = {'schema': 'AFI_DATASET_MANIFEST_V1', 'dataset_id': 'fixture-data', 'version': 'v1', 'evidence_class': 'SYNTHETIC', 'source': {'id': 'fixture', 'provider': 'SYNTHETIC', 'license_id': 'SYNTHETIC_FIXTURE', 'license_sha256': 'a' * 64, 'permission_status': 'SYNTHETIC_ONLY', 'permissions': ['OFFLINE_RESEARCH']}, 'acquired_at': MONDAY, 'generated_at': MONDAY, 'period_start': FRIDAY, 'period_end': MONDAY, 'content_sha256': '', 'record_count': 2, 'assets': [asset], 'quality': {'max_missing_fraction': 0, 'min_history_per_asset': 2}, 'revision_policy': 'AS_PUBLISHED_APPEND_ONLY', 'availability_basis': 'AS_PUBLISHED_ARCHIVE', 'universe_policy': 'POINT_IN_TIME_WITH_DELISTED'}
    return manifest, payload


def review(m, p):
    m = copy.deepcopy(m)
    raw = encode(p)
    m["content_sha256"] = hashlib.sha256(raw).hexdigest()
    m["record_count"] = len(p["records"])
    return review_dataset(encode(m), raw, asof=ASOF)


def bound_forecast(r):
    issue = datetime(2026, 10, 16, 20, 1, tzinfo=UTC)
    start, target = datetime.fromisoformat(FRIDAY), datetime.fromisoformat(MONDAY)
    f = Forecast("f", A, "US_EQUITY", "1D", issue, target, start, start, start,
                 100, 110, "baseline", "v1", "fixture-data", r.content_sha256, "b"*64, "SYNTHETIC",
                 dataset_manifest_sha256=r.manifest_sha256, dataset_version="v1")
    o = Outcome("f", A, "US_EQUITY", target, target, target, 120, "fixture", "v1", "SYNTHETIC")
    return f, o


def test_valid_dataset_binds_hash_version_input_calendar_outcome_and_metrics():
    r = review(*fixture())
    assert r.status == "ACCEPTED_SYNTHETIC" and r.expected_n == 2 and r.missing_n == 0
    f, o = bound_forecast(r)
    result = score_dataset_forecasts(r, [f], [o], asof=ASOF)
    assert result["scored_n"] == 1 and result["dataset_integrity_verified"]
    assert result["cohorts"][0]["mape_percent"] == pytest.approx(100/12)
    assert not result["dataset_authenticated"] and not result["production_approved"]
    assert not result["calibration_established"] and not r.independently_authenticated


@pytest.mark.parametrize("field,value", [
    ("availability_basis", "LATEST_DOWNLOAD"), ("universe_policy", "CURRENT_SURVIVORS"),
    ("revision_policy", "OVERWRITE"), ("generated_at", "2026-10-21T00:00:00+00:00"),
    ("acquired_at", "2026-10-15T00:00:00+00:00"), ("version", ""),
])
def test_refuse_manifest_leakage_and_unsupported_policies(field, value):
    m, p = fixture(); m[field] = value
    with pytest.raises(ForecastEvidenceRefused): review(m, p)


@pytest.mark.parametrize("field,value", [
    ("timezone", "UTC"), ("calendar", "WEEKDAYS"), ("granularity", "INTRADAY"),
    ("asset_class", "ETF"), ("dividend_policy", "TOTAL_RETURN"), ("freshness_seconds", True),
])
def test_asset_session_and_adjustment_conventions_are_explicit(field, value):
    m, p = fixture(); m["assets"][0][field] = value
    with pytest.raises(ForecastEvidenceRefused): review(m, p)


@pytest.mark.parametrize("field,value", [
    ("observed_at", "2026-10-17T20:00:00+00:00"),
    ("available_at", "2026-10-21T00:00:00+00:00"),
    ("available_at", "2026-10-15T00:00:00+00:00"),
    ("observed_at", "2026-10-16T20:00:00"), ("source_id", "other"),
    ("raw_price", -1), ("value", True), ("value", 99),
    ("applied_action_ids", ["future-split"]),
])
def test_record_refusals(field, value):
    m, p = fixture(); p["records"][0][field] = value
    with pytest.raises(ForecastEvidenceRefused): review(m, p)


def test_duplicate_identity_revision_and_simultaneous_conflict():
    for change in ({}, {"record_id": "other"}, {"record_id": "other", "revision": "v2", "value": 101, "raw_price": 101}):
        m, p = fixture(); p["records"].append({**p["records"][0], **change})
        with pytest.raises(ForecastEvidenceRefused): review(m, p)


def test_late_revision_is_not_visible_to_earlier_forecast():
    m, p = fixture()
    revised = {**p["records"][0], "record_id": "r2", "revision": "v2", "raw_price": 105, "value": 105,
               "available_at": "2026-10-19T19:00:00+00:00"}
    p["records"].append(revised)
    r = review(m, p); f, o = bound_forecast(r)
    assert select_asof(r.observations, asset_id=A, asset_class="US_EQUITY", cutoff=f.issued_at,
                       max_age=timedelta(days=4))["record"].value == 100
    score_dataset_forecasts(r, [f], [o], asof=ASOF)
    with pytest.raises(ForecastEvidenceRefused):
        score_dataset_forecasts(r, [replace(f, reference_price=105)], [o], asof=ASOF)
    revised["revision"] = "v1"
    with pytest.raises(ForecastEvidenceRefused): review(m, p)


def test_missing_and_empty_histories_refuse_skill_not_zero_fill():
    for records in ([], [fixture()[1]["records"][0]]):
        m, p = fixture(); p["records"] = records
        r = review(m, p)
        assert r.status == "INSUFFICIENT_EVIDENCE" and r.missing_n == 2-len(records)
        with pytest.raises(ForecastEvidenceRefused): score_dataset_forecasts(r, [], [], asof=ASOF)


def test_historical_permission_declaration_does_not_authenticate_rights():
    for status in ("DECLARED", "UNKNOWN", "DENIED"):
        m, p = fixture(); m["evidence_class"] = "HISTORICAL"; m["source"]["permission_status"] = status
        m["source"]["provider"] = "unverified-provider"; m["source"]["license_id"] = "claimed-license"
        r = review(m, p)
        assert r.status == "BLOCKED_AUTHORIZATION"
        assert "PROVIDER_RIGHTS" in r.reasons[0]
        with pytest.raises(ForecastEvidenceRefused): score_dataset_forecasts(r, [], [], asof=ASOF)


def test_content_corruption_duplicate_json_fields_and_bounds():
    m, p = fixture(); raw = encode(p); m["content_sha256"] = hashlib.sha256(raw).hexdigest()
    for changed in (raw+b" ", b'{"schema":1,"schema":2}', b'{"schema":NaN}', b"x"*5_000_001):
        with pytest.raises(ForecastEvidenceRefused): review_dataset(encode(m), changed, asof=ASOF)
    m["secret"] = "not-permitted"
    with pytest.raises(ForecastEvidenceRefused): review_dataset(encode(m), raw, asof=ASOF)


def test_source_receipt_commitments_are_validated_and_carried_into_review():
    m, p = fixture()
    record = p["records"][0]
    record["source_sha256"] = "a"*64
    revision = hashlib.sha256(encode({'asset_id': record['asset_id'],
                                     'observed_at': record['observed_at'],
                                     'received_at': record['available_at'],
                                     'value': record['value'],
                                     'source_sha256': record['source_sha256']})+b'\n').hexdigest()
    record["record_id"] = record["revision"] = revision
    r = review(m, p)
    assert r.status == "ACCEPTED_SYNTHETIC"
    action = {'action_id': 'split', 'asset_id': A, 'kind': 'SPLIT',
              'effective_at': MONDAY, 'available_at': FRIDAY, 'amount': 2,
              'economic_unit': 'NEW_SHARES_PER_OLD_SHARE', 'source_id': 'fixture',
              'source_sha256': 'b'*64}
    p["actions"] = [action]
    assert review(m, p).status == "ACCEPTED_SYNTHETIC"
    for field, value in (("source_sha256", "not-a-hash"), ("revision", "unbound")):
        bad = copy.deepcopy(p)
        bad["records"][0][field] = value
        with pytest.raises(ForecastEvidenceRefused):
            review(m, bad)
    for field, value in (("economic_unit", "USD_PER_SHARE"), ("source_id", ""),
                         ("source_sha256", "not-a-hash")):
        bad = copy.deepcopy(p)
        bad["actions"][0][field] = value
        with pytest.raises(ForecastEvidenceRefused):
            review(m, bad)
    for time in ("2025-12-31T00:00:00+00:00", "2026-10-20T20:00:00+00:00"):
        bad = copy.deepcopy(p)
        bad["actions"][0]["effective_at"] = time
        bad["universe"][0].update(delisted_at="2026-10-20T20:00:00+00:00",
                                  delisting_available_at=MONDAY)
        with pytest.raises(ForecastEvidenceRefused):
            review(m, bad)
    bad = copy.deepcopy(p)
    del bad["actions"][0]["source_sha256"]
    with pytest.raises(ForecastEvidenceRefused):
        review(m, bad)


def test_split_adjustment_requires_known_effective_action_and_correct_ratio():
    m, p = fixture(); m["assets"][0]["price_policy"] = "SPLIT_ADJUSTED"
    p["actions"] = [{'action_id': 'split', 'asset_id': A, 'kind': 'SPLIT', 'effective_at': '2026-10-19T13:30:00+00:00', 'available_at': '2026-10-18T00:00:00+00:00', 'amount': 2}]
    old = p["records"][0]
    old.update(available_at="2026-10-19T19:00:00+00:00", value=50, applied_action_ids=["split"])
    assert review(m, p).status == "ACCEPTED_SYNTHETIC"
    for change in ({"value": 51}, {"applied_action_ids": []}, {"available_at": FRIDAY}):
        bad = copy.deepcopy(p); bad["records"][0].update(change)
        with pytest.raises(ForecastEvidenceRefused): review(m, bad)


def test_dividend_is_explicitly_price_return_only_and_cross_split_forecast_refused():
    m, p = fixture()
    p["actions"] = [{'action_id': 'div', 'asset_id': A, 'kind': 'DIVIDEND', 'effective_at': MONDAY, 'available_at': FRIDAY, 'amount': 2}]
    r = review(m, p); f, o = bound_forecast(r)
    assert score_dataset_forecasts(r, [f], [o], asof=ASOF)["scored_n"] == 1
    p["actions"][0]["kind"] = "SPLIT"
    r = review(m, p); f, o = bound_forecast(r)
    with pytest.raises(ForecastEvidenceRefused, match="Cross-split"):
        score_dataset_forecasts(r, [f], [o], asof=ASOF)


@pytest.mark.parametrize("field,value", [("reference_price", 99), ("dataset_version", "v2"),
    ("dataset_sha256", "c"*64), ("dataset_manifest_sha256", "c"*64), ("horizon", "1W"),
    ("target_at", datetime(2026, 10, 17, 20, tzinfo=UTC)),
    ("input_available_at", datetime(2026, 10, 16, 19, tzinfo=UTC))])
def test_bound_forecasts_cannot_substitute_versions_inputs_or_targets(field, value):
    r = review(*fixture()); f, o = bound_forecast(r)
    with pytest.raises(ForecastEvidenceRefused):
        score_dataset_forecasts(r, [replace(f, **{field: value})], [o], asof=ASOF)


def test_review_substitution_and_unavailable_or_invented_outcome_refused():
    r = review(*fixture()); f, o = bound_forecast(r)
    with pytest.raises(ForecastEvidenceRefused):
        score_dataset_forecasts(replace(r, expected_n=1), [f], [o], asof=ASOF)
    for change in ({"price": 121}, {"revision": "v9"}, {"source_id": "other"},
                   {"available_at": ASOF+timedelta(days=1)}):
        with pytest.raises(ForecastEvidenceRefused):
            score_dataset_forecasts(r, [f], [replace(o, **change)], asof=ASOF)


def test_manifest_fingerprint_binds_conventions_and_legacy_fingerprint_is_stable():
    r = review(*fixture()); f, _ = bound_forecast(r)
    assert forecast_fingerprint(f) != forecast_fingerprint(replace(f, dataset_version="v2"))
    assert forecast_fingerprint(f) != forecast_fingerprint(replace(f, dataset_manifest_sha256="c"*64))


def test_equity_calendar_holiday_early_close_dst_and_unsupported_year():
    for times in (("2026-11-25T21:00:00+00:00", "2026-11-27T18:00:00+00:00"),
                  ("2026-03-06T21:00:00+00:00", "2026-03-09T20:00:00+00:00")):
        m, p = fixture()
        for row, t in zip(p["records"], times, strict=True): row.update(observed_at=t, available_at=t)
        m.update(period_start=times[0], period_end=times[1], acquired_at=times[1], generated_at=times[1])
        r = review_dataset(encode({**m, "content_sha256": hashlib.sha256(encode(p)).hexdigest()}),
                           encode(p), asof=datetime(2026,12,1,tzinfo=UTC))
        assert r.expected_n == 2 and r.missing_n == 0
    m, p = fixture(); m["period_start"] = "2025-12-31T00:00:00+00:00"
    with pytest.raises(ForecastEvidenceRefused, match="calendar"): review(m, p)


def test_crypto_and_etf_are_separate_asset_and_calendar_conventions():
    for asset_class in ("ETF", "CRYPTO"):
        m, p = fixture(); identity = asset_class+":TEST"
        a=m["assets"][0]; a.update(asset_id=identity,asset_class=asset_class)
        p["universe"][0]["asset_id"]=identity
        for row in p["records"]: row["asset_id"]=identity
        if asset_class=="CRYPTO":
            a.update(timezone="UTC",calendar="CRYPTO_24_7")
            times=("2026-10-18T00:00:00+00:00","2026-10-19T00:00:00+00:00")
            for row,t in zip(p["records"],times,strict=True): row.update(observed_at=t,available_at=t)
            m.update(period_start=times[0],period_end=times[1])
        assert review(m,p).status=="ACCEPTED_SYNTHETIC"


def test_delisted_records_are_covered_but_cannot_start_new_forecasts():
    m,p=fixture();p["universe"][0].update(delisted_at="2026-10-16T20:00:30+00:00",delisting_available_at=FRIDAY)
    p["records"]=p["records"][:1];m["quality"]["min_history_per_asset"]=2
    r=review(m,p)
    assert r.status=="INSUFFICIENT_EVIDENCE" and r.expected_n==1
    p["records"].append(fixture()[1]["records"][1])
    with pytest.raises(ForecastEvidenceRefused):review(m,p)


def protocol():
    t=datetime(2026,10,16,tzinfo=UTC)
    return [ReplayWindow("select",t,t+timedelta(hours=1),t+timedelta(hours=2)),
            ReplayWindow("holdout",t+timedelta(days=1),t+timedelta(days=2),None)],t+timedelta(hours=3)


def test_selection_protocol_deterministic_without_independent_unseen_claim():
    rows,freeze=protocol()
    a=audit_selection_protocol(rows,selection_ids=["select"],holdout_ids=["holdout"],frozen_at=freeze,asof=ASOF)
    b=audit_selection_protocol(rows[::-1],selection_ids=["select"],holdout_ids=["holdout"],frozen_at=freeze,asof=ASOF)
    assert a==b and not a["independently_unseen"] and not a["production_approved"]


@pytest.mark.parametrize("case", ["overlap","missing","duplicate","unknown","late-label","peek","future-freeze"])
def test_selection_and_holdout_contamination_refusals(case):
    rows,freeze=protocol();selection=["select"];holdout=["holdout"]
    if case=="overlap":holdout.append("select")
    if case=="missing":holdout=[]
    if case=="duplicate":selection.append("select")
    if case=="unknown":holdout=["unknown"]
    if case=="late-label":rows[0]=replace(rows[0],outcome_available_at=freeze)
    if case=="peek":rows[1]=replace(rows[1],issued_at=freeze-timedelta(seconds=1))
    if case=="future-freeze":freeze=ASOF+timedelta(seconds=1)
    with pytest.raises(ForecastEvidenceRefused):
        audit_selection_protocol(rows,selection_ids=selection,holdout_ids=holdout,frozen_at=freeze,asof=ASOF)


def test_embargo_purges_labels_at_boundary_and_late_publication():
    rows,freeze=protocol()
    rows += [ReplayWindow("late",freeze-timedelta(hours=1),freeze,freeze+timedelta(days=3))]
    plan=walk_forward_plan(rows,min_train=2,embargo=timedelta(days=1))
    assert all(f["status"]=="INSUFFICIENT_EVIDENCE" for f in plan["folds"])

@pytest.mark.parametrize("mutation", ["asset-list", "record-list", "source-list", "missing-license", "quality-list",
                                      "universe-id-list", "actions-id-list", "unknown-field", "record-count"])
def test_malformed_nested_evidence_has_typed_refusal(mutation):
    m,p=fixture()
    if mutation=="asset-list":m["assets"][0]=[]
    if mutation=="record-list":p["records"][0]=[]
    if mutation=="source-list":m["source"]=[]
    if mutation=="missing-license":m["source"].pop("license_sha256")
    if mutation=="quality-list":m["quality"]=[]
    if mutation=="universe-id-list":p["universe"][0]["asset_id"]=[]
    if mutation=="actions-id-list":p["actions"]=[{'action_id': 'a', 'asset_id': [], 'kind': 'SPLIT', 'effective_at': FRIDAY, 'available_at': FRIDAY, 'amount': 2}]
    if mutation=="unknown-field":p["records"][0]["credential"]="not-allowed"
    if mutation=="record-count":m["record_count"]=True
    if mutation=="record-count":
        raw=encode(p);m["content_sha256"]=hashlib.sha256(raw).hexdigest()
        with pytest.raises(ForecastEvidenceRefused):review_dataset(encode(m),raw,asof=ASOF)
    else:
        with pytest.raises(ForecastEvidenceRefused):review(m,p)


def test_fifth_session_target_is_distinct_from_one_week():
    m,p=fixture()
    times=[FRIDAY,MONDAY,"2026-10-20T20:00:00+00:00","2026-10-21T20:00:00+00:00",
           "2026-10-22T20:00:00+00:00","2026-10-23T20:00:00+00:00"]
    p["records"]=[{**p["records"][0],"record_id":f"r{i}","observed_at":t,"available_at":t,
                    "raw_price":100+i,"value":100+i} for i,t in enumerate(times)]
    m.update(period_end=times[-1],acquired_at=times[-1],generated_at=times[-1])
    later=datetime(2026,10,24,tzinfo=UTC)
    raw=encode(p);m.update(content_sha256=hashlib.sha256(raw).hexdigest(),record_count=6)
    r=review_dataset(encode(m),raw,asof=later);f,o=bound_forecast(r)
    target=datetime.fromisoformat(times[-1])
    f=replace(f,horizon="5D",target_at=target)
    o=replace(o,target_at=target,observed_at=target,available_at=target,price=105)
    assert score_dataset_forecasts(r,[f],[o],asof=later)["scored_n"]==1
    with pytest.raises(ForecastEvidenceRefused):
        score_dataset_forecasts(r,[replace(f,horizon="1W")],[o],asof=later)


def test_stale_reference_refused_and_missing_outcome_stays_pending():
    m,p=fixture();m["assets"][0]["freshness_seconds"]=1
    r=review(m,p);f,o=bound_forecast(r)
    with pytest.raises(ForecastEvidenceRefused):score_dataset_forecasts(r,[f],[o],asof=ASOF)
    r=review(*fixture());f,o=bound_forecast(r)
    result=score_dataset_forecasts(r,[f],[],asof=ASOF)
    assert result["scored_n"]==0 and result["pending_n"]==1
    assert result["cohorts"][0]["mape_percent"] is None


def test_no_change_baseline_zero_never_claims_infinite_skill():
    from app.backtest.forecast_evaluation import score_forecasts
    r=review(*fixture());f,o=bound_forecast(r)
    result=score_forecasts([f],[replace(o,price=100)],asof=ASOF)
    assert result["cohorts"][0]["mae_ratio_to_no_change"] is None
    assert not result["calibration_established"]

def test_legacy_fingerprint_bytes_remain_compatible_and_manifest_binding_is_complete():
    from dataclasses import asdict
    r=review(*fixture());f,_=bound_forecast(r)
    legacy=replace(f,dataset_manifest_sha256=None,dataset_version=None)
    values={k:(v.astimezone(UTC).isoformat() if isinstance(v,datetime) else v) for k,v in asdict(legacy).items()
            if k not in ("dataset_manifest_sha256","dataset_version","model_configuration_sha256")}
    assert legacy.model_configuration_sha256 is None
    # Independently verified against the preserved pre-configuration implementation.
    assert forecast_fingerprint(legacy)=="6dc6dae717f10194487ec5905ce1b44a25f9c309823648f8333f98bca925960f"
    assert forecast_fingerprint(legacy)==hashlib.sha256(encode(values)).hexdigest()
    with pytest.raises(ForecastEvidenceRefused):forecast_fingerprint(replace(f,dataset_version=None))


def test_models_and_manifest_versions_are_never_pooled():
    from app.backtest.forecast_evaluation import score_forecasts
    r=review(*fixture());f,o=bound_forecast(r)
    g=replace(f,forecast_id="g",model_version="v2",dataset_version="v2")
    report=score_forecasts([f,g],[o,replace(o,forecast_id="g")],asof=ASOF)
    assert len(report["cohorts"])==2
    assert all(c["n"]==1 and c["status"]=="INSUFFICIENT_EVIDENCE" for c in report["cohorts"])
