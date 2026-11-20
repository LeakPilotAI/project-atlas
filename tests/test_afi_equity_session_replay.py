import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from app.backtest.forecast_baselines import fit_baseline, predict_baseline
from app.backtest.forecast_dataset import _grid, review_dataset, score_dataset_forecasts
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from app.backtest.forecast_replay import replay_baselines
from test_afi_dataset_integrity import encode, fixture


def equity_history(issue,asset_class='US_EQUITY',late_target=False):
    m,p=fixture();asset=m['assets'][0];asset.update(asset_id=asset_class+':FIXTURE',asset_class=asset_class)
    p['universe'][0]['asset_id']=asset['asset_id']
    start=issue-timedelta(days=35);end=min(issue+timedelta(days=12),datetime(2028,12,31,23,tzinfo=UTC))
    times=_grid(start,end,asset);prototype=p['records'][0]
    p['records']=[{**prototype,'record_id':f'e{i}','asset_id':asset['asset_id'],'observed_at':t.isoformat(),'available_at':t.isoformat(),'raw_price':100+i,'value':100+i} for i,t in enumerate(times)]
    if late_target:
        target=next(r for r in p['records'] if datetime.fromisoformat(r['observed_at'])>issue)
        target['available_at']=(datetime.fromisoformat(target['observed_at'])+timedelta(days=1)).isoformat()
    raw=encode(p);m.update(period_start=times[0].isoformat(),period_end=times[-1].isoformat(),record_count=len(times),content_sha256=hashlib.sha256(raw).hexdigest(),acquired_at=end.isoformat(),generated_at=end.isoformat())
    asof=end+timedelta(days=2)
    return review_dataset(encode(m),raw,asof=asof),asset['asset_id'],asof


@pytest.mark.parametrize('asset_class',['US_EQUITY','ETF'])
@pytest.mark.parametrize('issued,target',[
 ('2026-11-25T21:01:00+00:00','2026-11-27T18:00:00+00:00'),
 ('2026-03-06T21:01:00+00:00','2026-03-09T20:00:00+00:00'),
 ('2026-10-30T20:01:00+00:00','2026-11-02T21:00:00+00:00'),
 ('2028-12-28T21:01:00+00:00','2028-12-29T21:00:00+00:00'),
])
def test_next_equity_close_uses_holiday_dst_early_close_and_calendar_boundary(asset_class,issued,target):
    issued=datetime.fromisoformat(issued);r,asset,asof=equity_history(issued,asset_class)
    m=fit_baseline(r,asset_id=asset,issued_at=issued,evidence_asof=asof,lookback=5)
    f=predict_baseline(m,r,evidence_asof=asof)
    assert f.target_at==datetime.fromisoformat(target)
    assert score_dataset_forecasts(r,[f],[],asof=asof)['pending_n']==1


def test_unknown_fifth_close_still_refuses_at_calendar_end():
    issued=datetime(2028,12,28,21,1,tzinfo=UTC);r,asset,asof=equity_history(issued)
    m=fit_baseline(r,asset_id=asset,issued_at=issued,evidence_asof=asof,lookback=5,horizon='5D')
    with pytest.raises(ForecastEvidenceRefused):predict_baseline(m,r,evidence_asof=asof)


def test_delayed_close_publication_remains_pending_until_known_vintage():
    issued=datetime(2026,11,25,21,1,tzinfo=UTC);r,asset,asof=equity_history(issued,late_target=True)
    early=replay_baselines(r,asset_id=asset,issued_times=[issued],evidence_asof=asof,outcome_asof=datetime(2026,11,27,19,tzinfo=UTC),lookback=5)
    late=replay_baselines(r,asset_id=asset,issued_times=[issued],evidence_asof=asof,outcome_asof=datetime(2026,11,28,19,tzinfo=UTC),lookback=5)
    assert early['score']['pending_n']==1 and late['score']['scored_n']==1
    assert early['forecasts']==late['forecasts'] and not late['production_approved']
