import asyncio

import app.api.command_center as command_api
import app.api.diagnostics as diagnostics_api


def _reset_caches():
    command_api._command_cache = None
    command_api._command_task = None
    diagnostics_api._research_cache = None
    diagnostics_api._research_task = None


def test_command_center_summary_offloads_sync_work(monkeypatch):
    _reset_caches()
    calls=[]
    async def fake_to_thread(fn,*args,**kwargs):
        calls.append((fn,args,kwargs))
        return {"ok":True}
    monkeypatch.setattr(asyncio,"to_thread",fake_to_thread)
    monkeypatch.setattr(command_api.perp_manual_service,"snapshot",lambda:{"setups":[]})
    result=asyncio.run(command_api.command_center_summary())
    assert result=={"ok":True}
    assert len(calls)==1
    assert calls[0][0] is command_api._build_summary


def test_research_endpoint_offloads_sync_work(monkeypatch):
    _reset_caches()
    calls=[]
    async def fake_to_thread(fn,*args,**kwargs):
        calls.append((fn,args,kwargs))
        return {"research":"ok"}
    monkeypatch.setattr(asyncio,"to_thread",fake_to_thread)
    result=asyncio.run(diagnostics_api.diagnostics_research())
    assert result=={"research":"ok"}
    assert len(calls)==1
    assert calls[0][0] is diagnostics_api._research_payload


def test_command_center_warming_fallback_is_read_only_and_no_live():
    row=command_api._warming_summary({"running":True,"market_count":232,"setups":[]})
    assert row["mode"]=="READ_ONLY"
    assert row["execution"]=="NO_ORDER_ACTIONS"
    assert row["operational_surface"]["state"]=="WARMING"
    assert row["operational_surface"]["live_capital_allowed"] is False
    assert row["operational_surface"]["automatic_real_money_execution"] is False


def test_research_warming_fallback_is_read_only_and_no_live():
    row=diagnostics_api._research_warming_payload()
    assert row["operational_surface"]["state"]=="WARMING"
    assert row["operational_surface"]["read_only"] is True
    assert row["operational_surface"]["live_capital_allowed"] is False
    assert row["operational_surface"]["automatic_real_money_execution"] is False


def test_operational_budgets_fit_inside_desktop_smoke_timeout():
    assert command_api._COMMAND_RESPONSE_BUDGET_SECONDS < 5.0
    assert diagnostics_api._RESEARCH_RESPONSE_BUDGET_SECONDS < 5.0


def test_manual_observability_scan_runs_off_api_thread(monkeypatch):
    import threading
    import app.api.perp_manual as api
    owner = threading.get_ident()
    workers = []
    def scan(setups):
        workers.append(threading.get_ident())
        return {"checked": True}
    monkeypatch.setattr(api, "build_paper_observability", scan)
    monkeypatch.setattr(api.perp_manual_service, "snapshot", lambda: {"setups": []})
    monkeypatch.setattr(api.perp_setup_paper_mirror, "status", lambda: {})
    assert asyncio.run(api.manual_perps())["auto_paper"]["observability"]["checked"]
    assert asyncio.run(api.manual_perp_board(limit=12))["auto_paper"]["observability"]["checked"]
    assert len(workers) == 2 and all(worker != owner for worker in workers)


def test_paper_stats_scan_runs_off_event_loop(monkeypatch):
    import threading
    from app.services.paper_journal import paper_journal
    owner = threading.get_ident()
    def scan():
        assert threading.get_ident() != owner
        return {"closed": 3}
    monkeypatch.setattr(paper_journal, "_stats_snapshot", scan)
    assert asyncio.run(paper_journal.stats()) == {"closed": 3}


def test_validation_history_reports_use_fastapi_worker_threads(monkeypatch):
    import threading
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.validation import router
    import app.services.edge_diagnostics as edge
    import app.services.paper_validation as validation
    loop_thread = []
    worker_threads = []
    app = FastAPI()
    app.include_router(router)
    @app.middleware("http")
    async def capture_thread(request, call_next):
        loop_thread.append(threading.get_ident())
        return await call_next(request)
    def edge_report():
        worker_threads.append(threading.get_ident())
        return {"ok": True, "live_capital_allowed": False}
    def readiness(rows):
        worker_threads.append(threading.get_ident())
        return dict.fromkeys(["closed_trades", "observed_wr", "observed_expectancy", "total_r", "data_sufficiency", "statistical_stability", "performance", "risk", "data_integrity", "conclusion", "milestone"], 0)
    monkeypatch.setattr(edge, "edge_report", edge_report)
    monkeypatch.setattr(validation, "load_paper_closes", lambda: [])
    monkeypatch.setattr(validation, "readiness_report", readiness)
    monkeypatch.setattr(validation, "uncertainty", lambda rows: {})
    with TestClient(app) as client:
        assert client.get("/api/validation/edge").status_code == 200
        assert client.get("/api/validation/summary").status_code == 200
    assert len(worker_threads) == 2
    assert all(worker not in loop_thread for worker in worker_threads)
