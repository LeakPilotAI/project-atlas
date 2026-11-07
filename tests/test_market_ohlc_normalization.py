"""Validated OHLC types agree with storage and the browser without history rewrites."""
import copy
import json
import sqlite3
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from app.investment.offline_research import ResearchInputRefused, validated_candles

from scripts.observation_runtime import market_replay

STAMP = datetime(2026, 10, 20, 14, tzinfo=UTC)
NOW = STAMP + timedelta(seconds=70)


def candle():
    return {'timestamp': STAMP, 'Open': '100', 'High': '102', 'Low': '99', 'Close': '101', 'Volume': '120'}


@pytest.mark.parametrize('field', ['Open', 'High', 'Low', 'Close'])
def test_valid_numeric_strings_become_finite_numbers_without_mutation(field):
    raw = candle()
    before = copy.deepcopy(raw)
    result = validated_candles('SPY', [raw], now=NOW)[0]
    assert type(result[field]) is float
    assert result[field] == float(raw[field])
    assert raw == before


@pytest.mark.parametrize('present', [[], ['Open'], ['High', 'Low']])
def test_optional_ohlc_fields_are_not_invented(present):
    raw = candle()
    for field in ['Open', 'High', 'Low']:
        if field not in present:
            del raw[field]
    result = validated_candles('SPY', [raw], now=NOW)[0]
    for field in ['Open', 'High', 'Low']:
        assert (field in result) == (field in present)
        if field in present:
            assert type(result[field]) is float


@pytest.mark.parametrize('field,value', [('High','NaN'), ('Low','Infinity'), ('Open',True), ('High','98'), ('Low','103')])
def test_invalid_ohlc_never_becomes_a_normalized_bar(field, value):
    raw = candle()
    raw[field] = value
    with pytest.raises(ResearchInputRefused):
        validated_candles('SPY', [raw], now=NOW)


def payload():
    return {'chart': {'error': None, 'result': [{'meta': {'symbol': 'SPY', 'currency': 'USD', 'dataGranularity': '1m'},
        'timestamp': [int(STAMP.timestamp())], 'indicators': {'quote': [{'open': ['100'], 'high': ['102'], 'low': ['99'], 'close': ['101'], 'volume': ['120']}]}}]}}


def test_string_ohlc_persists_reopens_and_actual_browser_accepts(tmp_path):
    path = tmp_path/'fixture.sqlite'
    with sqlite3.connect(path) as connection:
        store = market_replay.ReplayStore(connection)
        assert store.ingest(payload(), observed_at=NOW, asset_class='US_ETF') == 1
        assert store.ingest(payload(), observed_at=NOW+timedelta(seconds=1), asset_class='US_ETF') == 0
    with sqlite3.connect(path) as connection:
        store = market_replay.ReplayStore(connection)
        value = store.snapshot(['SPY'], now=NOW)
        value['quote_rows'] = store.quote_snapshot(['SPY'], now=NOW)
        assert all(type(value['rows'][0][field]) is float for field in ['open','high','low','close'])
    exported = tmp_path/'response.json'
    exported.write_text(json.dumps(value), encoding='utf-8')
    view = Path(__file__).resolve().parents[1]/'frontend/offline/market-replay/view.cjs'
    code = "const fs=require('node:fs');const a=require(process.argv[1]);const v=a.parseExport(fs.readFileSync(process.argv[2],'utf8'));if(v.rows[0].open!==100||v.rows[0].high!==102)throw Error('wrong prices');"
    result = subprocess.run(['C:/Program Files/nodejs/node.exe','-e',code,str(view),str(exported)], capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stdout+result.stderr


def test_prior_string_record_is_not_silently_rewritten(tmp_path, monkeypatch):
    with sqlite3.connect(tmp_path/'fixture.sqlite') as connection:
        store = market_replay.ReplayStore(connection)
        original = market_replay.validated_candles
        def legacy(*args, **kwargs):
            rows = original(*args, **kwargs)
            return [{**row, **{field: str(int(row[field])) for field in ['Open','High','Low']}} for row in rows]
        with monkeypatch.context() as scoped:
            scoped.setattr(market_replay, 'validated_candles', legacy)
            assert store.ingest(payload(), observed_at=NOW, asset_class='US_ETF') == 1
        before = connection.execute('SELECT digest,body FROM replay_bars').fetchall()
        with pytest.raises(ResearchInputRefused, match='Conflicting retained bar'):
            store.ingest(payload(), observed_at=NOW+timedelta(seconds=1), asset_class='US_ETF')
        assert connection.execute('SELECT digest,body FROM replay_bars').fetchall() == before

@pytest.mark.parametrize('field,value',[('Open',100),('High',102),('Low',99),('Open',100.0),('High',102.0),('Low',99.0)])
def test_existing_numeric_ohlc_preserves_representation(field,value):
    raw=candle()
    raw[field]=value
    result=validated_candles('SPY',[raw],now=NOW)[0]
    assert type(result[field]) is type(value)
    assert result[field]==value
