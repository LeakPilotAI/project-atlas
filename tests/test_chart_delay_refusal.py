import copy
import hashlib
import json
import sqlite3

import pytest
from test_chart_archive import NOW, prepare, run
from test_market_replay_integration import fixture

from scripts.observation_runtime.bar_vintages import BarVintageStore
from scripts.observation_runtime.chart_provenance import chart_provenance
from scripts.observation_runtime.market_replay import ReplayStore, normalize_chart


@pytest.mark.parametrize('delay',[1,15,True,None,'15',-1,86401])
@pytest.mark.parametrize('sink',['normalize','current','vintage'])
def test_explicit_unknown_unit_delay_cannot_enter_current_research(delay,sink):
    from datetime import timedelta
    payload=fixture(NOW-timedelta(seconds=70));payload['chart']['result'][0]['meta']['exchangeDataDelayedBy']=delay
    original=copy.deepcopy(payload)
    if sink=='normalize':
        with pytest.raises(ValueError):normalize_chart(payload,observed_at=NOW,asset_class='US_ETF')
    else:
        with sqlite3.connect(':memory:') as db:
            store=(ReplayStore if sink=='current' else BarVintageStore)(db)
            with pytest.raises(ValueError):store.ingest(payload,observed_at=NOW,asset_class='US_ETF')
            table='replay_bars' if sink=='current' else 'replay_bar_receipts'
            assert db.execute('SELECT count(*) FROM '+table).fetchone()[0]==0
    assert payload==original


def test_absent_or_zero_delay_preserves_original_normalized_and_current_bytes():
    from datetime import timedelta
    payload=fixture(NOW-timedelta(seconds=70));expected=normalize_chart(payload,observed_at=NOW,asset_class='US_ETF')
    payload['chart']['result'][0]['meta']['exchangeDataDelayedBy']=0
    assert normalize_chart(payload,observed_at=NOW,asset_class='US_ETF')==expected
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db);assert store.ingest(payload,observed_at=NOW,asset_class='US_ETF')==1
        assert store.snapshot(['SPY'],now=NOW)['rows'][0]['price']==101


def test_delayed_source_is_still_retained_as_explicit_unverified_diagnostic(tmp_path):
    from datetime import timedelta
    payload=fixture(NOW-timedelta(seconds=70));payload['chart']['result'][0]['meta']['exchangeDataDelayedBy']=15
    raw=json.dumps(payload).encode();report=chart_provenance(raw,observed_at=NOW,asset_class='US_ETF',expected_sha256=hashlib.sha256(raw).hexdigest())
    assert report['provider_reported_delay']==15 and report['provider_delay_unit']=='UNVERIFIED'
    assert report['live_status']=='NOT_ESTABLISHED' and report['network_authorized'] is False
    inputs,outputs,_,_=prepare(tmp_path,payload)
    assert run(inputs,outputs)['status']=='SYNTHETIC_CHART_ARCHIVED'


@pytest.mark.parametrize('mode',[None,1,'yes'])
def test_diagnostic_escape_requires_exact_boolean(mode):
    from datetime import timedelta
    with pytest.raises(ValueError):normalize_chart(fixture(NOW-timedelta(seconds=70)),observed_at=NOW,asset_class='US_ETF',diagnostic_only=mode)


def test_delayed_archived_source_cannot_bypass_source_replay_preflight(tmp_path):
    from datetime import timedelta

    from test_source_vintages import setup

    from scripts.observation_runtime.source_replay_export import export_source_replay

    payload=fixture(NOW-timedelta(seconds=70));payload['chart']['result'][0]['meta']['exchangeDataDelayedBy']=15
    parent=tmp_path/'source';parent.mkdir();inputs,outputs,_,_=prepare(parent,payload);result=run(inputs,outputs)
    spec={'receipt':result['receipt'],'expected_sha256':result['receipt_sha256']};bundle,source_request=setup(tmp_path,[(outputs,spec)])
    raw=b'[]\n';(bundle/'references.json').write_bytes(raw)
    request={'schema':'ATLAS_SOURCE_REPLAY_REQUEST_V1','source_request':source_request,'references':'references.json',
             'expected_references_sha256':hashlib.sha256(raw).hexdigest(),'decisions':[NOW.isoformat()]}
    (bundle/'replay.json').write_text(json.dumps(request));before={p.name:p.read_bytes() for p in bundle.iterdir()}
    with pytest.raises(ValueError):export_source_replay(bundle_root=bundle,request_name='replay.json',output_root=bundle)
    assert before=={p.name:p.read_bytes() for p in bundle.iterdir()}
