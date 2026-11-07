"""Receipt chronology does not become a claim of live provider freshness."""
import copy
import hashlib
import json
from datetime import datetime, timedelta

import pytest
from test_daily_afi_bridge import POLICY, chart, days, encode, end, universe

from scripts.observation_runtime import daily_availability as availability
from scripts.observation_runtime.daily_afi_export import export_daily_dataset


def bundle(root, observations):
    snapshots = []
    for payload, receipt in observations:
        raw = encode(payload)
        pin = hashlib.sha256(raw).hexdigest()
        (root/(pin+'.json')).write_bytes(raw)
        snapshots.append({'file': pin+'.json', 'sha256': pin, 'received_at': receipt.isoformat()})
    request = {'schema': 'ATLAS_SYNTHETIC_DAILY_EXPORT_REQUEST_V1', 'snapshots': snapshots,
               'symbol': 'SPY', 'asset_class': 'US_ETF', 'universe': universe(), 'dataset_id': 'availability-fixture',
               'version': 'v1', 'asof': observations[-1][1].isoformat(), **POLICY}
    (root/'request.json').write_bytes(encode(request))
    result = export_daily_dataset(bundle_root=root, request_name='request.json', output_root=root)
    return {'bundle_root': root, 'binding_name': result['binding'], 'expected_binding_sha256': result['binding'][:-5],
            'asof': observations[-1][1].isoformat(), 'max_first_receipt_age_seconds': 60}


def basic(root):
    return bundle(root, [(chart(['2026-10-15', '2026-10-16']), end('2026-10-16')+timedelta(minutes=1))])


def test_historical_batch_is_not_live_freshness_even_with_recent_receipt(tmp_path):
    receipt = datetime.fromisoformat('2026-10-19T13:00:00+00:00')
    args = bundle(tmp_path, [(chart(['2026-10-15', '2026-10-16']), receipt)])
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    report = availability.daily_availability(**args)
    assert report['receipt_pattern'] == 'SINGLE_RECEIPT_HISTORICAL_BATCH'
    assert report['first_receipt_age'] == {'n': 2, 'minimum_seconds': 234000., 'median_seconds': 277200.,
                                           'p95_seconds': 320400., 'maximum_seconds': 320400.}
    assert report['latest_cash_close_age_seconds'] == 234000
    assert report['time_since_last_supplied_receipt_seconds'] == 0
    assert report['first_receipt_budget_exceeded_n'] == 2
    assert report['provider_data_freshness'] == 'NOT_ESTABLISHED'
    assert report['provider_service_health'] == 'NOT_OBSERVED'
    assert report['vendor_latency_verified'] is report['startup_authorized'] is False
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


def test_incremental_receipts_exact_retries_and_unchanged_confirmations_stay_separate(tmp_path):
    calendar = ['2026-10-16', '2026-10-19', '2026-10-20']
    observations = [(chart(calendar[:i+1]), end(day)+timedelta(minutes=1)) for i, day in enumerate(calendar)]
    observations.insert(1, observations[0])
    observations.append((observations[-1][0], observations[-1][1]+timedelta(hours=1)))
    report = availability.daily_availability(**bundle(tmp_path, observations))
    assert report['receipt_pattern'] == 'DISTINCT_FIRST_RECEIPTS'
    assert report['submitted_snapshot_n'] == 5 and report['effective_receipt_n'] == 4
    assert report['exact_retry_n'] == report['previously_seen_payload_receipt_n'] == 1
    assert report['unchanged_close_confirmations_n'] == 6
    assert report['observation_n'] == report['price_record_n'] == 3
    assert report['price_revision_n'] == 0
    assert report['first_receipt_age']['minimum_seconds'] == report['first_receipt_age']['maximum_seconds'] == 60
    assert report['revision_receipt_age']['minimum_seconds'] is None
    assert report['latest_cash_close_age_seconds'] == 3660
    assert report['time_since_last_supplied_receipt_seconds'] == 0
    assert report['first_receipt_budget_exceeded_n'] == 0


def test_late_value_changes_and_reversions_keep_original_availability(tmp_path):
    original = chart(['2026-10-15', '2026-10-16'])
    corrected = copy.deepcopy(original)
    corrected['chart']['result'][0]['indicators']['quote'][0]['close'][0] += .25
    stamp = end('2026-10-16')+timedelta(minutes=1)
    report = availability.daily_availability(**bundle(tmp_path, [(original, stamp), (corrected, stamp+timedelta(minutes=1)),
                                                                (original, stamp+timedelta(minutes=2))]))
    assert report['price_revision_n'] == 2 and report['observation_n'] == 2
    assert report['rows'][0]['first_known_receipt'] == stamp.isoformat()
    assert report['rows'][0]['price_revision_n'] == 2
    assert report['revision_after_first_receipt_age'] == {'n': 2, 'minimum_seconds': 60., 'median_seconds': 90.,
                                                       'p95_seconds': 120., 'maximum_seconds': 120.}
    assert report['revision_receipt_age']['minimum_seconds'] == 86520
    assert report['previously_seen_payload_receipt_n'] == 1


@pytest.mark.parametrize('calendar,seconds,close', [
    (['2026-03-06', '2026-03-09'], 30, '2026-03-09T20:00:00+00:00'),
    (['2026-11-25', '2026-11-27'], 7, '2026-11-27T18:00:00+00:00'),
])
def test_dst_and_holiday_early_closes_use_actual_cash_close(calendar, seconds, close, tmp_path):
    args = bundle(tmp_path, [(chart(calendar[:i+1]), end(day)+timedelta(seconds=seconds)) for i, day in enumerate(calendar)])
    args['max_first_receipt_age_seconds'] = seconds
    report = availability.daily_availability(**args)
    assert report['latest_cash_close'] == close
    assert report['first_receipt_age']['minimum_seconds'] == report['first_receipt_age']['maximum_seconds'] == seconds
    assert report['first_receipt_budget_exceeded_n'] == 0
    args['max_first_receipt_age_seconds'] -= 1
    assert availability.daily_availability(**args)['first_receipt_budget_exceeded_n'] == 2


def test_missing_cash_session_remains_insufficient_not_imputed(tmp_path):
    args = bundle(tmp_path, [(chart(['2026-10-14', '2026-10-16']), end('2026-10-16'))])
    report = availability.daily_availability(**args)
    assert report['dataset_status'] == 'INSUFFICIENT_EVIDENCE'
    assert report['observation_n'] == 2 and len(report['rows']) == 2
    assert report['monitoring_completeness_verified'] is False


@pytest.mark.parametrize('budget', [True, -1, 1.5, float('inf'), 1_000_000_001])
def test_invalid_budgets_refuse(tmp_path, budget):
    args = basic(tmp_path)
    args['max_first_receipt_age_seconds'] = budget
    with pytest.raises(ValueError):
        availability.daily_availability(**args)


# Deliberately construct an input with no timezone, to exercise refusal.
@pytest.mark.parametrize('asof', [None, 'bad-clock', '2026-10-16T20:00:30+00:00', datetime.fromisoformat('2026-10-20T00:00:00')])
def test_missing_naive_or_earlier_cutoff_refuses(tmp_path, asof):
    args = basic(tmp_path)
    args['asof'] = asof
    with pytest.raises(ValueError):
        availability.daily_availability(**args)


@pytest.mark.parametrize('fault', ['pin', 'raw', 'records', 'audit'])
def test_source_commitment_refusal_without_mutation(tmp_path, fault):
    args = basic(tmp_path)
    binding = json.loads((tmp_path/args['binding_name']).read_bytes())
    if fault == 'pin': args['expected_binding_sha256'] = '0'*64
    else:
        target = binding['request']['snapshots'][0]['file'] if fault == 'raw' else binding['artifacts'][fault]
        (tmp_path/target).write_bytes(b'{}')
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(ValueError):
        availability.daily_availability(**args)
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


def test_summary_denominators_include_rows_outside_display_cap(tmp_path):
    calendar = days(150)
    args = bundle(tmp_path, [(chart(calendar), end(calendar[-1])+timedelta(minutes=1))])
    report = availability.daily_availability(**args)
    assert report['first_receipt_age']['n'] == report['observation_n'] == 150
    assert report['displayed_observation_n'] == len(report['rows']) == 128
    assert report['first_receipt_budget_exceeded_n'] == 149
    assert report['first_receipt_age']['maximum_seconds'] == (end(calendar[-1])+timedelta(minutes=1)-end(calendar[0])).total_seconds()


def test_export_cli_is_checked_idempotent_and_no_live_health_claim(tmp_path, capsys):
    args = basic(tmp_path)
    result = availability.export_daily_availability(**args, output_root=tmp_path)
    assert availability.export_daily_availability(**args, output_root=tmp_path) == result
    html = (tmp_path/result['html']).read_text(encoding='utf-8')
    assert '<script' not in html and "connect-src 'none'" in html
    assert 'not a fresh live feed' in html
    assert availability.main(['--bundle-root', str(tmp_path), '--binding', args['binding_name'],
                              '--expected-binding-sha256', args['expected_binding_sha256'], '--asof', args['asof'],
                              '--max-first-receipt-age-seconds', '60', '--output-root', str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out) == result


def test_partial_export_failure_is_not_success_and_keeps_json(tmp_path, monkeypatch):
    args = basic(tmp_path)
    original = availability.publish_research_text
    before = set(tmp_path.iterdir())

    def fail(root, value, **kwargs):
        if kwargs['extension'] == '.html':
            raise OSError('synthetic full storage')
        return original(root, value, **kwargs)

    monkeypatch.setattr(availability, 'publish_research_text', fail)
    with pytest.raises(OSError):
        availability.export_daily_availability(**args, output_root=tmp_path)
    added = set(tmp_path.iterdir())-before
    assert len(added) == 1
    assert json.loads(added.pop().read_bytes())['schema'] == 'ATLAS_SYNTHETIC_DAILY_AVAILABILITY_V1'


def test_missing_revisions_have_unavailable_distribution_not_zero(tmp_path):
    report = availability.daily_availability(**basic(tmp_path))
    assert report['revision_receipt_age'] == {'n': 0, 'minimum_seconds': None, 'median_seconds': None,
                                             'p95_seconds': None, 'maximum_seconds': None}


def test_timezone_equivalent_retries_are_one_effective_receipt(tmp_path):
    payload = chart(['2026-10-15', '2026-10-16'])
    first = datetime.fromisoformat('2026-10-16T20:01:00+00:00')
    same = datetime.fromisoformat('2026-10-16T15:01:00-05:00')
    report = availability.daily_availability(**bundle(tmp_path, [(payload, first), (payload, same)]))
    assert report['exact_retry_n'] == 1 and report['effective_receipt_n'] == 1
    assert report['unchanged_close_confirmations_n'] == 0
    assert len(report['first_receipt_groups']) == 1


def test_mixed_first_receipt_groups_do_not_claim_continuous_monitoring(tmp_path):
    calendar = ['2026-10-14', '2026-10-15', '2026-10-16']
    args = bundle(tmp_path, [(chart(calendar[:2]), end(calendar[1])+timedelta(minutes=1)),
                             (chart(calendar), end(calendar[2])+timedelta(minutes=1))])
    report = availability.daily_availability(**args)
    assert report['receipt_pattern'] == 'MIXED_RECEIPT_GROUPS'
    assert [row['newly_known_close_n'] for row in report['first_receipt_groups']] == [2, 1]
    assert report['monitoring_completeness_verified'] is False


def test_zero_age_boundary_and_single_observation_stay_explicit(tmp_path):
    args = bundle(tmp_path, [(chart(['2026-10-16']), end('2026-10-16'))])
    args['max_first_receipt_age_seconds'] = 0
    report = availability.daily_availability(**args)
    assert report['receipt_pattern'] == 'ONE_OBSERVATION_ONLY'
    assert report['first_receipt_age']['n'] == 1
    assert report['first_receipt_age']['maximum_seconds'] == report['first_receipt_budget_exceeded_n'] == 0
    assert report['dataset_status'] == 'INSUFFICIENT_EVIDENCE'
    assert report['provider_data_freshness'] == 'NOT_ESTABLISHED'


def test_artifact_change_after_initial_source_verification_refuses(tmp_path, monkeypatch):
    args = basic(tmp_path)
    original = availability.verify_daily_export
    calls = 0

    def changed(**kwargs):
        nonlocal calls
        result = original(**kwargs)
        calls += 1
        if calls == 1:
            binding = json.loads((tmp_path/args['binding_name']).read_bytes())
            path = tmp_path/binding['artifacts']['audit']
            value = json.loads(path.read_bytes())
            value['repeated_close_n'] += 1
            path.write_bytes(encode(value))
        return result

    monkeypatch.setattr(availability, 'verify_daily_export', changed)
    before = set(tmp_path.iterdir())
    with pytest.raises(ValueError, match='commitment changed'):
        availability.daily_availability(**args)
    assert set(tmp_path.iterdir()) == before
