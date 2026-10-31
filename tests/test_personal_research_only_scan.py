"""Existing scanner/scoring with synthetic providers; no legacy or network IO."""
import asyncio
from datetime import UTC, datetime

import pytest
from app.investment import ingest as ingestion
from app.investment import scan
from app.investment.ingest import InvestmentIngest
from app.investment.scan_settings import ScanSettings
from app.investment.universe import InvestmentUniverse
from test_investment_phase5 import _entry, bars_from_closes, healthy_snap


def setup(tmp_path):
    universe = InvestmentUniverse([_entry('MSFT'), _entry('SPY')])
    bars = bars_from_closes([100.0]*280 + [50.0]*20)
    def snapshot(symbol):
        result=healthy_snap(universe.get(symbol))
        stamp=datetime(2026,10,28,14,0,tzinfo=UTC)
        for value in (result.price,*result.fundamentals.values(),*result.valuation.values()):
            value.timestamp=value.effective_timestamp=value.retrieved_at=stamp
        result.retrieved_at=stamp
        return result
    class Price:
        async def get_price(self, symbol): return snapshot(symbol).price
        async def get_daily_ohlcv(self, symbol, **kwargs): return bars
    class Fundamentals:
        async def get_all(self, symbol): return snapshot(symbol).fundamentals
    class Valuation:
        async def get_all(self, symbol): return snapshot(symbol).valuation
    ingest = InvestmentIngest(universe=universe, price=Price(), fundamentals=Fundamentals(),
        valuation=Valuation(), history_root=tmp_path, persist=False, read_only=True)
    scanner = scan.InvestmentScanner(settings=ScanSettings(enabled=False, persist=False,
        notify_discord=False, inter_symbol_delay_seconds=0, max_retries=0), universe=universe,
        ingest=ingest, history_root=tmp_path, persist=False, research_only=True)
    return scanner, ingest, bars


def test_real_scanner_scores_two_instruments_without_legacy_or_financial_effects(tmp_path, monkeypatch):
    scanner, ingest, bars = setup(tmp_path)
    def forbidden(*a, **kw): raise AssertionError('UNAUTHORIZED_LEGACY_OR_WRITE_CALL')
    for name in ('load_portfolio','bootstrap_universe_if_missing','load_latest_snapshot',
                 'set_equity_tape','save_latest_snapshot','append_scan_log','append_observation',
                 'append_research','append_move_event','deliver_investment_alert','configure_provider_health'):
        monkeypatch.setattr(scan, name, forbidden)
    monkeypatch.setattr(ingestion, 'append_bars', forbidden)
    monkeypatch.setattr(ingestion, 'persist_snapshot', forbidden)
    monkeypatch.setattr(scanner, '_paper_book', forbidden)
    monkeypatch.setattr(scanner, '_port', forbidden)
    before = list(tmp_path.rglob('*'))
    report = asyncio.run(scanner.run_once(now=datetime(2026,10,28,14,0,tzinfo=UTC)))
    assert report.evaluated == 2 and report.failed == 0 and report.alerts_emitted >= 0
    assert {obs.symbol for obs in report.observations} == {'MSFT','SPY'}
    assert all(obs.research.price == 50.0 and obs.research.input_snapshot for obs in report.observations)
    assert ingest.research_bars('MSFT') == tuple(bars)
    assert list(tmp_path.rglob('*')) == before
    assert scanner.paper is None and scanner._portfolio_override is None


@pytest.mark.parametrize('damage', ['persist','notify','background','paper','portfolio','history','mode','ingest-mode'])
def test_changed_research_capability_refuses_before_any_data_call(tmp_path, damage):
    scanner, ingest, _ = setup(tmp_path)
    if damage == 'persist': scanner._persist_override = True
    elif damage == 'notify': scanner.settings.notify_discord = True
    elif damage == 'background': scanner.settings.enabled = True
    elif damage == 'paper': scanner.paper = object()
    elif damage == 'portfolio': scanner._portfolio_override = object()
    elif damage == 'history': ingest.history_root = tmp_path/'foreign'
    elif damage == 'mode': scanner.research_only = False
    elif damage == 'ingest-mode': ingest.read_only = False
    with pytest.raises(ValueError, match='RESEARCH_ONLY'):
        asyncio.run(scanner.run_once())
    assert list(tmp_path.rglob('*')) == []


def test_no_background_start_and_no_implicit_ingest_dependencies(tmp_path):
    scanner, _, _ = setup(tmp_path)
    with pytest.raises(ValueError, match='NO_BACKGROUND'):
        asyncio.run(scanner.start())
    with pytest.raises(ValueError, match='EXPLICIT_INPUTS'):
        InvestmentIngest(read_only=True, persist=False)


def test_ingest_readonly_mode_cannot_be_changed_into_a_writer(tmp_path):
    scanner, ingest, _ = setup(tmp_path)
    ingest.read_only = False
    with pytest.raises(ValueError, match='MODE_CHANGED'):
        asyncio.run(ingest.ingest_symbol(scanner._universe_override.get('MSFT')))
    assert list(tmp_path.rglob('*')) == []
