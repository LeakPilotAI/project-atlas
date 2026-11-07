"""Explicit contradictory provider metadata cannot be relabeled as US equity/ETF."""
import copy
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from app.investment.offline_research import ResearchInputRefused
from test_market_replay_integration import fixture, quote_fixture

from scripts.observation_runtime.market_replay import (
    ReplayStore,
    normalize_chart,
    normalize_quote,
)


@pytest.mark.parametrize('kind',['chart','quote'])
@pytest.mark.parametrize('field,value',[
    ('exchangeTimezoneName','Europe/London'),('exchangeTimezoneName',None),
    ('exchangeTimezoneName',True),('instrumentType','CRYPTOCURRENCY'),('instrumentType','EQUITY'),
    ('quoteType','CRYPTOCURRENCY'),('quoteType',None),('quoteType','EQUITY'),
])
def test_explicit_contradictory_or_malformed_metadata_refuses_before_storage(kind,field,value):
    event=datetime(2026,10,20,14,tzinfo=UTC);now=event+timedelta(seconds=70)
    payload=fixture(event) if kind=='chart' else quote_fixture(event)
    meta=payload['chart']['result'][0]['meta'] if kind=='chart' else payload['quoteResponse']['result'][0]
    meta[field]=value;original=copy.deepcopy(payload)
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db)
        with pytest.raises(ResearchInputRefused):
            (store.ingest if kind=='chart' else store.ingest_quote)(payload,observed_at=now,asset_class='US_ETF')
        assert db.execute('SELECT count(*) FROM replay_bars').fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM replay_quotes').fetchone()[0]==0
    assert payload==original


@pytest.mark.parametrize('kind',['chart','quote'])
@pytest.mark.parametrize('asset,instrument',[('US_ETF','ETF'),('US_EQUITY','EQUITY')])
def test_consistent_metadata_preserves_original_normalized_representation(kind,asset,instrument):
    event=datetime(2026,10,20,14,tzinfo=UTC);now=event+timedelta(seconds=70)
    payload=fixture(event) if kind=='chart' else quote_fixture(event)
    normalize=normalize_chart if kind=='chart' else normalize_quote
    expected=normalize(payload,observed_at=now,asset_class=asset)
    meta=payload['chart']['result'][0]['meta'] if kind=='chart' else payload['quoteResponse']['result'][0]
    meta.update(exchangeTimezoneName='America/New_York',instrumentType=instrument,quoteType=instrument)
    assert normalize(payload,observed_at=now,asset_class=asset)==expected
