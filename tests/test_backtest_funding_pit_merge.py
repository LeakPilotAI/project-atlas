from pathlib import Path
import csv
import pytest
from app.backtest.funding_pit_merge import merge


def _bars(path:Path):
    with path.open('w',newline='') as fh:
        w=csv.DictWriter(fh,fieldnames=['timestamp','symbol','timeframe','open','high','low','close','volume'])
        w.writeheader()
        for ts in ['2024-07-01T00:00:00Z','2024-07-01T00:05:00Z','2024-07-01T00:10:00Z']:
            w.writerow({'timestamp':ts,'symbol':'BTC','timeframe':'5m','open':1,'high':1,'low':1,'close':1,'volume':1})


def _funding(path:Path,rows):
    with path.open('w',newline='') as fh:
        w=csv.DictWriter(fh,fieldnames=['timestamp','funding_rate']);w.writeheader()
        for ts,rate in rows:w.writerow({'timestamp':ts,'funding_rate':rate})


def test_exact_event_maps_to_containing_half_open_bar(tmp_path:Path):
    b=tmp_path/'b.csv';f=tmp_path/'f.csv';o=tmp_path/'o.csv';_bars(b)
    _funding(f,[('2024-07-01T00:00:00.182000Z','0.001'),('2024-07-01T00:07:00Z','-0.002')])
    r=merge(bars_path=b,funding_path=f,output=o)
    rows=list(csv.DictReader(o.open()))
    assert [float(x['funding_rate']) for x in rows]==[0.001,-0.002,0.0]
    assert r['funding_events_merged']==2
    assert r['forward_fill_used'] is False and r['interpolation_used'] is False


def test_multiple_events_in_same_bar_sum_exactly(tmp_path:Path):
    b=tmp_path/'b.csv';f=tmp_path/'f.csv';o=tmp_path/'o.csv';_bars(b)
    _funding(f,[('2024-07-01T00:01:00Z','0.001'),('2024-07-01T00:04:59Z','0.002')])
    merge(bars_path=b,funding_path=f,output=o)
    rows=list(csv.DictReader(o.open()))
    assert float(rows[0]['funding_rate'])==pytest.approx(0.003)


def test_out_of_window_event_is_not_synthesized(tmp_path:Path):
    b=tmp_path/'b.csv';f=tmp_path/'f.csv';o=tmp_path/'o.csv';_bars(b)
    _funding(f,[('2024-06-30T23:00:00Z','0.1'),('2024-07-01T00:10:00Z','0.2')])
    r=merge(bars_path=b,funding_path=f,output=o)
    rows=list(csv.DictReader(o.open()))
    assert [float(x['funding_rate']) for x in rows]==[0.0,0.0,0.2]
    assert r['funding_events_merged']==1


def test_duplicate_funding_timestamp_fails_closed(tmp_path:Path):
    b=tmp_path/'b.csv';f=tmp_path/'f.csv';_bars(b)
    _funding(f,[('2024-07-01T00:00:00Z','0.1'),('2024-07-01T00:00:00Z','0.2')])
    with pytest.raises(RuntimeError,match='unique ascending'):
        merge(bars_path=b,funding_path=f,output=tmp_path/'o.csv')
