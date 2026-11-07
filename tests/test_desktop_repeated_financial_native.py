"""Reconstruct real QD engine/native handles over the SAME immutable account."""
import copy
import hashlib
import os
from pathlib import Path

import pytest
from qd_autonomous_native_fixture import AutonomousNativePublication, build
from test_quality_dips_autonomous_paper import candidate, monitor


def test_repeated_desktop_financial_sessions_preserve_history_and_capacity(tmp_path):
    confinement=Path(os.environ['ATLAS_AUTO_RUNTIME_ROOT'])
    assert tmp_path.is_relative_to(confinement)
    x=build(tmp_path)
    try:
        n=x.n
        assert n.engine.stop()=='STOPPED'
        count=0;retained={};remaining=x.store.remaining_operations()
        for i in range(3):
            # Release/reopen actual Windows financial handles, never provision/reset.
            x.store.close();x.target.close()
            target=type(x.target)(str(tmp_path/'projection'),x.projection_id)
            store=type(x.store)(str(tmp_path/'source'),x.pins,projection=target)
            x.target=target;x.store=store;x.service.store=store
            n.engine=n.new()
            n.engine.publication=AutonomousNativePublication(store=store,manifest=n.m)
            assert n.engine.grant is None
            n.now[0]+=1
            grant=copy.deepcopy(n.grant);grant.update(session_id='desktop-'+str(i),issued_at=n.now[0],expires_at=n.now[0]+3600)
            n.engine.start(grant)
            b=candidate(n)
            b['observation']['observation_id']='fresh-ranked-observation-'+str(i)
            b['publication'].update(generation=i+1,source_revision=i+1)
            from test_quality_dips_autonomous_paper import quote
            result=n.engine.step('entry-'+str(i),bundles=[b],quotes=[quote(n,b)])
            assert result['filled'],result
            assert monitor(n,b,'exit-'+str(i),'101',{'classification':'THESIS_BROKEN'})['filled']
            assert n.engine.stop()=='STOPPED'
            day=__import__('datetime').datetime.fromtimestamp(n.now[0],__import__('datetime').UTC).date().isoformat()
            x.service.publish(day,n.now[0]);count+=2
            cut=store.verified_cut()
            assert cut['state']['revision']==count
            assert store.remaining_operations()==remaining-count
            assert all(p['remaining']=='0' for p in cut['state']['positions'].values())
            for path,value in retained.items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==value
            retained.update({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (tmp_path/'source').iterdir() if p.is_file()})
            # This exact completed grant can never restart the account.
            with pytest.raises(ValueError):n.new().start(grant)
        assert len(x.service.history())==3
        assert len(store.verified_cut()['acknowledged_operations'])==6
    finally:
        x.store.close();x.target.close();x.close()
