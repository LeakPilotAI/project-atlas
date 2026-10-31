"""Exact, browser-compatible share counts, not float-rounded observations."""
import json
import sqlite3
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from app.investment.offline_research import ResearchInputRefused, validated_candles

from scripts.observation_runtime.market_replay import ReplayStore

STAMP = datetime(2026, 10, 20, 14, tzinfo=UTC)
NOW = STAMP + timedelta(seconds=70)


def candle(volume):
    return {'timestamp': STAMP, 'Open': 100, 'High': 102, 'Low': 99, 'Close': 101, 'Volume': volume}


@pytest.mark.parametrize('volume', [2**53, 2**53+1, str(2**53), str(2**53+1),
    '1.0000000000000000001', '1e-400',
    '9007199254740990.9', True, -1, 'NaN', 'Infinity'])
def test_inexact_fractional_or_unsafe_volume_refuses(volume):
    with pytest.raises(ResearchInputRefused):
        validated_candles('SPY', [candle(volume)], now=NOW)


@pytest.mark.parametrize('volume,expected', [(0,0), ('0',0), (120,120), ('120.0',120),
    (120.0,120), (2**53-1,2**53-1), (str(2**53-1),2**53-1), ('1.2e2',120)])
def test_safe_integral_volume_preserved(volume, expected):
    row = validated_candles('SPY', [candle(volume)], now=NOW)[0]
    assert type(row['Volume']) is int
    assert row['Volume'] == expected


def payload(volume):
    return {'chart': {'error': None, 'result': [{'meta': {'symbol': 'SPY', 'currency': 'USD', 'dataGranularity': '1m'},
        'timestamp': [int(STAMP.timestamp()), int((STAMP+timedelta(minutes=1)).timestamp())],
        'indicators': {'quote': [{'open': [100,100], 'high': [102,102], 'low': [99,99], 'close': [101,101], 'volume': [100,volume]}]}}]}}


@pytest.mark.parametrize('volume', [2**53, '9007199254740990.9'])
def test_invalid_later_volume_never_partially_persists(tmp_path, volume):
    with sqlite3.connect(tmp_path/'fixture.sqlite') as connection:
        store = ReplayStore(connection)
        with pytest.raises(ResearchInputRefused):
            store.ingest(payload(volume), observed_at=NOW+timedelta(minutes=1), asset_class='US_ETF')
        assert connection.execute('SELECT COUNT(*) FROM replay_bars').fetchone()[0] == 0


def test_maximum_safe_volume_reopens_and_is_accepted_by_actual_browser(tmp_path):
    path = tmp_path/'fixture.sqlite'
    with sqlite3.connect(path) as connection:
        store = ReplayStore(connection)
        assert store.ingest(payload(str(2**53-1)), observed_at=NOW+timedelta(minutes=1), asset_class='US_ETF') == 2
    with sqlite3.connect(path) as connection:
        store = ReplayStore(connection)
        value = store.snapshot(['SPY'], now=NOW+timedelta(minutes=1))
        value['quote_rows'] = store.quote_snapshot(['SPY'], now=NOW+timedelta(minutes=1))
        assert value['rows'][0]['volume'] == 2**53-1
    export = tmp_path/'response.json'
    export.write_text(json.dumps(value), encoding='utf-8')
    view = Path(__file__).resolve().parents[1]/'frontend/offline/market-replay/view.cjs'
    code = "const fs=require('node:fs');const api=require(process.argv[1]);const v=api.parseExport(fs.readFileSync(process.argv[2],'utf8'));if(v.rows[0].volume!==Number.MAX_SAFE_INTEGER)throw Error('wrong shares');"
    result = subprocess.run(['C:/Program Files/nodejs/node.exe','-e',code,str(view),str(export)], capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stdout+result.stderr
