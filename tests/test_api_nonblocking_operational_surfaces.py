import asyncio

import app.api.command_center as command_api
import app.api.diagnostics as diagnostics_api


def test_command_center_summary_offloads_sync_work(monkeypatch):
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
    calls=[]
    async def fake_to_thread(fn,*args,**kwargs):
        calls.append((fn,args,kwargs))
        return {"research":"ok"}
    monkeypatch.setattr(asyncio,"to_thread",fake_to_thread)
    result=asyncio.run(diagnostics_api.diagnostics_research())
    assert result=={"research":"ok"}
    assert len(calls)==1
    assert calls[0][0] is diagnostics_api._research_payload
