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
