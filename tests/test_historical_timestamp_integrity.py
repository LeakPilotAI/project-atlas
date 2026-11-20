import csv
from dataclasses import replace

import pytest
from app.backtest.historical import run_historical_backtest
from app.backtest.io import load_historical_contexts
from test_historical_backtest_foundation import bars


@pytest.mark.parametrize('times',[
 ['2026-01-01T00:00:00+00:00','2026-01-01T01:00:00+01:00'],
 ['2026-01-01T00:00:00-02:00','2026-01-01T01:00:00+00:00'],
 ['2026-01-01T00:00:00','2026-01-01T00:05:00'],
 ['2026-01-01T00:90:00Z','2026-01-01T00:95:00Z'],
])
def test_ambiguous_duplicate_or_backward_actual_times_are_refused(times):
    rows=[replace(b,timestamp=t) for b,t in zip(bars()[:2],times,strict=True)]
    with pytest.raises(ValueError):run_historical_backtest(rows,lambda _:None)


def test_lexical_order_does_not_reject_actual_forward_offset_times():
    times=['2026-01-01T01:00:00+02:00','2026-01-01T00:00:00+00:00']
    rows=[replace(b,timestamp=t) for b,t in zip(bars()[:2],times,strict=True)]
    result=run_historical_backtest(rows,lambda _:None)
    assert result['dataset']['first_timestamp']==times[0] and not result['live_capital_allowed']


@pytest.mark.parametrize('times,valid',[
 (['2026-01-01T00:00:00+00:00','2026-01-01T01:00:00+01:00'],False),
 (['2026-01-01T01:00:00+02:00','2026-01-01T00:00:00+00:00'],True),
])
def test_dataset_io_uses_same_actual_instant_contract(tmp_path,times,valid):
    path=tmp_path/'offsets.csv'
    with path.open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=['timestamp','symbol','timeframe','open','high','low','close','volume','open_interest_usd','volume_24h_usd','htf_trend'])
        writer.writeheader()
        for t in times:writer.writerow({'timestamp':t,'symbol':'BTC','timeframe':'5m','open':100,'high':101,'low':99,'close':100,'volume':1,'open_interest_usd':100000,'volume_24h_usd':200000,'htf_trend':'UP'})
    if valid:assert len(load_historical_contexts(path))==2
    else:
        with pytest.raises(ValueError):load_historical_contexts(path)
