import copy
import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from app.investment.offline_research import ResearchInputRefused
from test_market_replay_integration import fixture

from scripts.observation_runtime.chart_provenance import (
    chart_provenance,
    export_chart_provenance,
)

NOW=datetime(2026,10,20,14,1,10,tzinfo=UTC)


def raw_fixture():return json.dumps(fixture(NOW-timedelta(seconds=70))).encode()


def evaluate(raw):
    return chart_provenance(raw,observed_at=NOW,asset_class='US_ETF',expected_sha256=hashlib.sha256(raw).hexdigest())


def test_missing_optional_metadata_never_invents_realtime_or_adjustment_status():
    result=evaluate(raw_fixture())
    assert result['provider_reported_delay'] is None and result['provider_delay_unit']=='UNVERIFIED'
    assert result['adjusted_series']=='ABSENT' and result['adjustment_basis']=='UNVERIFIED'
    assert result['live_status']=='NOT_ESTABLISHED' and result['network_authorized'] is False
    assert result['rows'][0]['reported_adjusted_close'] is None


def test_reported_adjusted_series_never_replaces_chart_close():
    payload=json.loads(raw_fixture());original=copy.deepcopy(payload)
    payload['chart']['result'][0]['indicators']['adjclose']=[{'adjclose':[50.5]}]
    payload['chart']['result'][0]['meta']['exchangeDataDelayedBy']=15
    raw=json.dumps(payload).encode();result=evaluate(raw)
    assert result['rows'][0]['bar_close']==101 and result['rows'][0]['reported_adjusted_close']==50.5
    assert result['provider_reported_delay']==15 and result['provider_delay_unit']=='UNVERIFIED'
    assert result['source_sha256']!=hashlib.sha256(json.dumps(original).encode()).hexdigest()
    assert json.loads(raw)==payload


@pytest.mark.parametrize('series',[None,[],[{}],[{'adjclose':[]}],[{'adjclose':[None]}],
    [{'adjclose':[True]}],[{'adjclose':[-1]}],[{'adjclose':[0]}],[{'adjclose':[1,2]}],
    [{'adjclose':[1],'extra':1}],[{'adjclose':[float('inf')]}]])
def test_malformed_adjusted_series_refuses_without_export(tmp_path,series):
    payload=json.loads(raw_fixture());payload['chart']['result'][0]['indicators']['adjclose']=series
    raw=json.dumps(payload).encode()
    with pytest.raises((ResearchInputRefused,ValueError)):
        export_chart_provenance(raw,observed_at=NOW,asset_class='US_ETF',expected_sha256=hashlib.sha256(raw).hexdigest(),output_root=tmp_path)
    assert list(tmp_path.iterdir())==[]


@pytest.mark.parametrize('delay',[None,True,-1,86401,'0'])
def test_malformed_delay_cannot_be_silently_dropped(delay):
    payload=json.loads(raw_fixture());payload['chart']['result'][0]['meta']['exchangeDataDelayedBy']=delay
    with pytest.raises(ResearchInputRefused):evaluate(json.dumps(payload).encode())


def test_source_hash_is_wire_byte_identity_not_semantic_authentication():
    raw=raw_fixture()
    with pytest.raises(ResearchInputRefused):chart_provenance(raw+b' ',observed_at=NOW,asset_class='US_ETF',expected_sha256=hashlib.sha256(raw).hexdigest())
    changed=evaluate(raw+b' ')
    assert changed['source_authenticated'] is False and changed['source_sha256']!=evaluate(raw)['source_sha256']


def test_export_is_immutable_idempotent_and_readable_without_scripts(tmp_path):
    raw=raw_fixture();kwargs={'observed_at':NOW,'asset_class':'US_ETF','expected_sha256':hashlib.sha256(raw).hexdigest(),'output_root':tmp_path}
    result=export_chart_provenance(raw,**kwargs);before={p.name:p.read_bytes() for p in tmp_path.iterdir()}
    assert export_chart_provenance(raw,**kwargs)==result
    assert before=={p.name:p.read_bytes() for p in tmp_path.iterdir()}
    page=(tmp_path/result['dashboard']).read_text()
    assert '<script' not in page and 'unit unverified' in page and 'Chart close' in page
    provenance=json.loads((tmp_path/result['provenance']).read_bytes())
    assert provenance['report_sha256']==hashlib.sha256((tmp_path/result['report']).read_bytes()).hexdigest()


def test_adjusted_values_follow_event_identity_after_normalizer_sorts_source():
    payload=json.loads(raw_fixture());result=payload['chart']['result'][0]
    result['timestamp']=[int((NOW-timedelta(seconds=70)).timestamp()),int((NOW-timedelta(seconds=130)).timestamp())]
    for values in result['indicators']['quote'][0].values():values*=2
    result['indicators']['adjclose']=[{'adjclose':[80,90]}]
    report=evaluate(json.dumps(payload).encode())
    assert [r['reported_adjusted_close'] for r in report['rows']]==[90,80]
    assert report['rows'][0]['timestamp']<report['rows'][1]['timestamp']


@pytest.mark.parametrize('raw',[b'{"chart":{},"chart":{}}',b'{"x":NaN}',b'[]',b'null',b'x',b'\xff'])
def test_malformed_or_duplicate_json_is_not_diagnostic_evidence(raw):
    with pytest.raises(ValueError):evaluate(raw)


@pytest.mark.parametrize('stamp,session',[
    ('2026-10-20T12:00:00+00:00','PRE_MARKET'),
    ('2026-10-20T14:00:00+00:00','REGULAR'),
    ('2026-10-20T21:00:00+00:00','AFTER_HOURS'),
    ('2026-11-27T18:00:00+00:00','AFTER_HOURS'),
    ('2026-11-02T14:30:00+00:00','REGULAR'),
])
def test_diagnostic_retains_three_sessions_early_close_and_dst(stamp,session):
    event=datetime.fromisoformat(stamp);raw=json.dumps(fixture(event)).encode()
    report=chart_provenance(raw,observed_at=event+timedelta(seconds=70),asset_class='US_ETF',expected_sha256=hashlib.sha256(raw).hexdigest())
    assert report['rows'][0]['session']==session
    assert report['live_status']=='NOT_ESTABLISHED'
