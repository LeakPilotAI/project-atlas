"""No-write proposed label changes retain original population and explicit heads."""
import json

import pytest
from test_daily_holdout_continuation import setup
from test_daily_holdout_update import correction_flow, fixture, write

from scripts.observation_runtime import daily_holdout_update as update


@pytest.fixture(scope='module')
def seed(tmp_path_factory):
    root = tmp_path_factory.mktemp('preview-source')
    exported,companion = setup(root)
    return root,exported,companion


def snapshot(root):
    return {str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}


def test_preview_matches_publication_and_never_writes(tmp_path,seed,capsys):
    root,request = fixture(tmp_path,seed)
    name = write(root,request)
    before = snapshot(root)
    assert update.main(['--bundle-root',str(root),'--preview',name]) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview['published'] is False and preview['new_forecasts_created'] == 0
    assert preview['current_issued_n'] == 2 and preview['proposed_issued_states'] == {'RESOLVED':2}
    assert snapshot(root) == before
    impacts = [c['signed_error_impact'] for c in preview['cases']]
    assert sum(i['state'] == 'CURRENT_UNRESOLVED' for i in impacts) == 1
    assert all(i['proposed_signed_error'] is not None for i in impacts)
    assert all(i['proposed_minus_current_signed_error'] is None
               for i in impacts if i['state'] == 'CURRENT_UNRESOLVED')
    result = update.update_holdout_accountability(bundle_root=root,request_name=name)
    assert preview['proposed_issued_states'] == result['current_issued_states']
    assert preview['original_counts'] == result['original_counts']
    envelope = json.loads((root/result['browser_export']).read_bytes())
    published = json.loads(envelope['report_json'])
    rows = {row['forecast_sha256']:row for row in published['rows']}
    for case in preview['cases']:
        row = rows[case['forecast_sha256']]
        assert case['signed_error_impact']['proposed_actual'] == row['actual']
        assert case['signed_error_impact']['proposed_signed_error'] == row['forecast_point']-row['actual']

    again_before = snapshot(root)
    assert update.preview_holdout_update(bundle_root=root,request_name=name) == preview
    assert snapshot(root) == again_before


@pytest.mark.parametrize('fault', ['head','source_pin','clock'])
def test_bad_preview_refuses_without_writes(tmp_path,seed,fault):
    root,request = fixture(tmp_path,seed)
    if fault == 'head': request['expected_continuation_sha256'] = '0'*64
    if fault == 'source_pin': request['expected_daily_export_sha256'] = '0'*64
    if fault == 'clock': request['outcome_asof'] = '2099-01-01T00:00:00Z'
    name = write(root,request)
    before = snapshot(root)
    with pytest.raises(ValueError): update.preview_holdout_update(bundle_root=root,request_name=name)
    assert snapshot(root) == before


def test_correction_preview_and_current_head_repeat_do_not_create_samples(tmp_path,seed):
    root,first,second = correction_flow(tmp_path,seed)
    companion = json.loads((root/second['companion']).read_bytes())
    before = snapshot(root)
    correction = update.preview_holdout_update(bundle_root=root,request_name=companion['request'])
    assert snapshot(root) == before
    assert correction['new_forecasts_created'] == 0 and correction['published'] is False
    assert correction['current_issued_n'] == 2
    assert correction['current_issued_states'] == correction['proposed_issued_states'] == {'RESOLVED':2}
    assert sum(c['recorded_event'] == 'CORRECTION' and c['would_append'] for c in correction['cases']) == 1
    assert correction['proposed_append_events']['CORRECTION'] == 1
    changed = [c['signed_error_impact'] for c in correction['cases']
               if c['recorded_event'] == 'CORRECTION' and c['would_append']]
    assert len(changed) == 1 and changed[0]['state'] == 'FINITE'
    assert changed[0]['proposed_minus_current_signed_error'] == 10
    assert changed[0]['current_actual']-changed[0]['proposed_actual'] == 10

    request = json.loads((root/companion['request']).read_bytes())
    request['continuation'] = second['continuation']
    request['expected_continuation_sha256'] = second['continuation'].split('/')[-1][:-5]
    name = write(root,request)
    before = snapshot(root)
    repeated = update.preview_holdout_update(bundle_root=root,request_name=name)
    assert snapshot(root) == before
    assert repeated['proposed_append_n'] == 0 and repeated['proposed_append_events'] == {}
    assert all(c['signed_error_impact']['proposed_minus_current_signed_error'] == 0 for c in repeated['cases'])
    assert all(not c['would_append'] and c['previous_head'] == c['proposed_head'] for c in repeated['cases'])
    assert any(c['recorded_event'] == 'CORRECTION' for c in repeated['cases'])
    assert repeated['original_counts'] == first['original_counts'] == second['original_counts']
    assert repeated['independent_latest_head_established'] is False


def test_preview_refuses_request_changed_during_reconstruction(tmp_path,seed,monkeypatch):
    root,request = fixture(tmp_path,seed)
    name = write(root,request)
    before = snapshot(root)
    original = update.preview_outcome
    changed = False
    def change(*args, **kwargs):
        nonlocal changed
        record = original(*args, **kwargs)
        if not changed:
            target = root/name
            target.write_bytes(target.read_bytes()+b' ')
            changed = True
        return record
    monkeypatch.setattr(update,'preview_outcome',change)
    with pytest.raises(ValueError): update.preview_holdout_update(bundle_root=root,request_name=name)
    after = snapshot(root)
    assert changed and after.pop(name) == before.pop(name)+b' '
    assert after == before


@pytest.mark.parametrize('point,current,proposed,state,delta', [
    (100,99,101,'FINITE',-2),
    (1e300,100,101,'FINITE',-1),
    (100,None,101,'CURRENT_UNRESOLVED',None),
    (100,None,None,'CURRENT_UNRESOLVED',None),
])
def test_signed_preview_numeric_and_missing_outcomes(point,current,proposed,state,delta):
    row = {'forecast_point':point, 'actual':current, 'status':'RESOLVED' if current is not None else 'PENDING_TARGET'}
    record = {'status':'RESOLVED' if proposed is not None else 'PENDING_TARGET',
              'observation':{'value':proposed} if proposed is not None else None}
    value = update._signed_preview(row,record)
    assert value['state'] == state
    assert value['proposed_minus_current_signed_error'] == delta
    assert value['current_signed_error'] == (point-current if current is not None else None)
    assert value['proposed_signed_error'] == (point-proposed if proposed is not None else None)
