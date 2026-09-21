import asyncio
import threading
from types import SimpleNamespace


def test_cycle_summary_and_persistence_run_off_event_loop(monkeypatch, tmp_path):
    import app.investment.scan as module
    from app.investment.universe import InvestmentUniverse
    scanner = module.InvestmentScanner(universe=InvestmentUniverse([]), persist=True,
                                      fetch_state_path=tmp_path / 'fetch.json')
    for name in ('_ing', '_store', '_port', '_paper_book'):
        monkeypatch.setattr(scanner, name, lambda *args: None)
    monkeypatch.setattr(module, 'configure_provider_health', lambda **kwargs: None)
    monkeypatch.setattr(module, 'append_scan_log', lambda report: None)
    monkeypatch.setattr(module, 'set_equity_tape', lambda rows: None)
    monkeypatch.setattr(scanner, '_enrich_past', lambda **kwargs: None)
    calls = []
    monkeypatch.setattr(module, 'cycle_summary', lambda report: calls.append(('summary', threading.get_ident())) or {'ok': True})
    monkeypatch.setattr(module, 'save_last_cycle', lambda report: calls.append(('save', threading.get_ident(), report)))
    loop_thread = threading.get_ident()
    asyncio.run(scanner.run_once())
    assert [row[0] for row in calls] == ['summary', 'save']
    assert all(row[1] != loop_thread for row in calls)
    assert calls[-1][2] == {'ok': True}


def test_manual_endpoints_offload_status_scans(monkeypatch):
    import app.api.perp_manual as module
    calls = []
    monkeypatch.setattr(module.perp_manual_service, 'snapshot', lambda: {'setups': []})
    monkeypatch.setattr(module.perp_setup_paper_mirror, 'status', lambda: calls.append(threading.get_ident()) or {'verified': True})
    monkeypatch.setattr(module, 'build_paper_observability', lambda *args: {})
    monkeypatch.setattr(module, 'build_perp_board', lambda *args, **kwargs: [])
    loop_thread = threading.get_ident()
    assert asyncio.run(module.manual_perps())['auto_paper']['verified']
    assert asyncio.run(module.manual_perp_board(limit=8))['auto_paper']['verified']
    assert len(calls) == 2
    assert all(value != loop_thread for value in calls)


def test_manual_refresh_keeps_sync_async_and_offloads_journal(monkeypatch):
    import app.services.paper_pipeline_hooks as hooks
    import app.services.paper_journal as journal
    import app.services.perp_manual_service as manual
    import app.services.perp_setup_paper_mirror as mirror
    import app.services.perp_micro_coach as coach
    import app.services.v4_journal_observer as observer
    from app.services.perp_setup_paper_mirror import SOURCE
    calls = []
    loop_thread = threading.get_ident()
    async def refresh(self):
        assert threading.get_ident() == loop_thread
        return {'markets': [], 'setups': []}
    async def sync(*args):
        assert threading.get_ident() == loop_thread
        return {'ok': True}
    def rows(path):
        calls.append(threading.get_ident())
        return iter([{'source': SOURCE, 'trade_id': 'test-only', 'event': 'open'}])
    monkeypatch.setattr(manual.PerpManualService, '_atlas_auto_paper_hooked', False, raising=False)
    monkeypatch.setattr(manual.PerpManualService, 'refresh', refresh)
    monkeypatch.setattr(coach.PerpMicroCoach, '_atlas_pipeline_hooked', True, raising=False)
    monkeypatch.setattr(observer, 'install_paper_journal_observer', lambda obj: None)
    monkeypatch.setattr(journal, 'iter_jsonl', rows)
    monkeypatch.setattr(mirror.perp_setup_paper_mirror, 'sync', sync)
    hooks.apply()
    service = SimpleNamespace(last_snapshot={}, snapshot=lambda: {})
    asyncio.run(manual.PerpManualService.refresh(service))
    assert calls and all(value != loop_thread for value in calls)
    assert service.last_snapshot['auto_paper']['open_count'] == 1
