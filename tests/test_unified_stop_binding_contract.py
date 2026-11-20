"""Disposable integration of existing Stop binder/owner/SQLite ports. No native launch."""
import sqlite3
from types import SimpleNamespace
import pytest
from fastapi import FastAPI
from app.services.quality_dips_stop_bridge import enroll_unified_paper_stop_transport
from app.services.personal_paper_runtime import bind_personal_unified_paper_stop
from test_unified_paper_runtime import runtime
from test_personal_paper_runtime import installed

ORIGIN='http://127.0.0.1:18811'
TOKEN='synthetic-control-token-only-1234567890'

class Closer:
    def close_verified(self, roster):pytest.fail('Enrollment must not close processes')
    def verify_exit(self, roster):pytest.fail('Enrollment must not generate exit evidence')


def system():
    r=runtime();r.grant['session_id']='disposable-binder-contract'
    return r,FastAPI(),Closer()


def test_method_owner_and_guarded_sqlite_factory_are_forwarded_and_closed(tmp_path):
    r,app,owner=system();events=[]
    class Connection(sqlite3.Connection):
        def close(self):events.append('close');return super().close()
    def factory(*args,**kw):
        events.append('open');return sqlite3.connect(*args,**kw,factory=Connection)
    bridge=enroll_unified_paper_stop_transport(app,runtime=r,owned_close=owner,
        ledger_path=tmp_path/'stop.sqlite',origin=ORIGIN,token=TOKEN,connection_factory=factory)
    assert bridge.owned_close is owner and bridge.stop_ledger._connection_factory is factory
    bridge.stop_ledger.reserve_fresh(r.grant['session_id'],'SHUTDOWN_FLATTEN')
    assert bridge.stop_ledger.recover(r.grant['session_id'],'SHUTDOWN_FLATTEN')['state']=='SHUTDOWN_UNVERIFIED'
    assert events==['open','close']*4 and r.state=='RUNNING'
    assert any(route.path=='/_atlas/control/stop-session' for route in app.routes)


@pytest.mark.parametrize('owner',[lambda:True,object(),SimpleNamespace(close_verified=lambda r:True),SimpleNamespace(verify_exit=lambda r:True)])
def test_unusable_shutdown_owner_refuses_before_sqlite_or_route(tmp_path,owner):
    r,app,_=system();calls=[]
    with pytest.raises(ValueError,match='RUNTIME_AND_OWNER_REQUIRED'):
        enroll_unified_paper_stop_transport(app,runtime=r,owned_close=owner,
            ledger_path=tmp_path/'stop.sqlite',origin=ORIGIN,token=TOKEN,connection_factory=lambda *a,**k:calls.append(True))
    assert not calls and not (tmp_path/'stop.sqlite').exists()
    assert not any(route.path.startswith('/_atlas/') for route in app.routes)


def test_guarded_connection_refusal_is_not_replaced_by_plain_sqlite(tmp_path):
    r,app,owner=system();calls=[]
    def factory(*args,**kw):calls.append(True);raise OSError('DISPOSABLE_OWNER_RESERVATION_REFUSED')
    with pytest.raises(OSError,match='RESERVATION_REFUSED'):
        enroll_unified_paper_stop_transport(app,runtime=r,owned_close=owner,
            ledger_path=tmp_path/'stop.sqlite',origin=ORIGIN,token=TOKEN,connection_factory=factory)
    assert calls==[True] and not (tmp_path/'stop.sqlite').exists()
    assert not any(route.path.startswith('/_atlas/') for route in app.routes)


def test_prior_pending_intent_blocks_binding_without_replay(tmp_path):
    from app.services.paper_stop_receipt_ledger import PaperStopReceiptLedger
    r,app,owner=system();path=tmp_path/'stop.sqlite'
    ledger=PaperStopReceiptLedger(path);ledger.reserve_fresh(r.grant['session_id'],'SHUTDOWN_FLATTEN')
    with pytest.raises(ValueError,match='PRIOR_STOP_RECONCILIATION_REQUIRED'):
        enroll_unified_paper_stop_transport(app,runtime=r,owned_close=owner,
            ledger_path=path,origin=ORIGIN,token=TOKEN)
    assert ledger.recover(r.grant['session_id'],'SHUTDOWN_FLATTEN')['state']=='SHUTDOWN_UNVERIFIED'
    assert r.entry_closed.is_set() and not any(route.path.startswith('/_atlas/') for route in app.routes)


def test_personal_installation_preserves_owner_and_guarded_connection_port(tmp_path):
    r,app,owner=system();r.grant['test_only']=False
    p=installed(accounts={'QUALITY_DIPS':'a'*64,'HYPERLIQUID':'b'*64},
        ports={'lanes':r.lanes,'portfolio':r.portfolio,'clock':r.clock})
    r.installation=p.i;calls=[]
    def factory(*args,**kw):calls.append(True);return sqlite3.connect(*args,**kw)
    bridge=bind_personal_unified_paper_stop(app,runtime=r,installation=p.i,owned_close=owner,
        ledger_path=tmp_path/'stop.sqlite',origin=ORIGIN,token=TOKEN,connection_factory=factory)
    assert bridge.stop_ledger._connection_factory is factory and bridge.owned_close is owner
    assert calls==[True,True] and r.state=='RUNNING'
