import json
from datetime import UTC, datetime

import pytest
from app.backtest.forecast_cli import run
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from test_afi_baselines import ASOF, ASSET
from test_afi_cli import inputs
from test_afi_uncertainty import interval


def arguments(tmp_path):
    manifest,records,out=inputs(tmp_path);i=interval();path=tmp_path/'interval.json';path.write_text(json.dumps(i),encoding='utf-8')
    return {'manifest':manifest,'records':records,'output_root':out,'asset_id':ASSET,'issued_at':datetime(2026,10,17,0,1,tzinfo=UTC),'evidence_asof':ASOF,'lookback':5,'method':i['selection']['selected_method'],'interval_path':path}


def test_frozen_interval_cli_publication_and_identical_retry(tmp_path):
    args=arguments(tmp_path);result=run(**args)
    assert result['interval_binding']=='EXPLICIT_FROZEN_SYNTHETIC_ONLY' and not result['production_approved']
    out=args['output_root'];original={p.name:p.read_bytes() for p in out.iterdir()}
    assert run(**args)==result and original=={p.name:p.read_bytes() for p in out.iterdir()}
    artifact=json.loads((out/result['forecast_artifact']).read_bytes())
    assert artifact['forecast']['interval_level']==.8
    html=(out/result['dashboard']).read_text(encoding='utf-8');assert 'unverified coverage' in html


@pytest.mark.parametrize('change',['tampered','model','lookback','premature','malformed'])
def test_interval_cli_refuses_before_publication(tmp_path,change):
    args=arguments(tmp_path)
    if change=='tampered':
        i=json.loads(args['interval_path'].read_bytes());i['absolute_error_quantile']=999;args['interval_path'].write_text(json.dumps(i),encoding='utf-8')
    if change=='model':args['method']='ENDPOINT_DRIFT' if args['method']=='NO_CHANGE' else 'NO_CHANGE'
    if change=='lookback':args['lookback']=6
    if change=='premature':args['issued_at']=datetime(2026,10,1,0,1,tzinfo=UTC)
    if change=='malformed':args['interval_path'].write_bytes(b'{bad')
    with pytest.raises(ForecastEvidenceRefused):run(**args)
    assert not list(args['output_root'].iterdir())
