"""Bounded synthetic source/native/HTTP/actual WinForms acceptance only.

No operational enrollment, real account roots, provider clients or trade POSTs.
"""
import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import time
import uuid
from pathlib import Path

from source_publication_native_fixture import Publications
from test_unified_actual_http import host
from test_unified_actual_native_lanes import cycle
from unified_actual_lanes_fixture import build


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--browser-only',action='store_true');args=parser.parse_args()
    repo=Path(__file__).resolve().parents[1]
    confinement=Path(os.environ['ATLAS_PERP_ORDER_TEST_ROOT']);qd=Path(os.environ['ATLAS_UNIFIED_QD_TEST_ROOT'])
    assert confinement.parent==repo/'logs/diagnostics' and confinement.name.startswith('perp-order-custody-')
    assert qd.parent==repo/'logs/diagnostics' and qd.name.startswith('qd-auto-runtime-')
    root=confinement/('source-acceptance-'+uuid.uuid4().hex);root.mkdir()
    pub=Publications(root);s=build(root,confinement,qd,publication_factory=pub.factory)
    h=ready=gui=None
    try:
        s.r.start({'session_id':'synthetic-unified-session'});asyncio.run(cycle(s))
        order=next(iter(s.p.orders.snapshot()['state']['orders'].values()))['order']
        s.tick(s.clock()+1);s.p.packet['maker_fills'][order['order_id']]=s.p.fill_proof(order,quantity='0.6')
        pub.publish();asyncio.run(cycle(s))
        h,token=host(s);ready=h.start()
        if args.browser_only:
            before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for base in (s.root,s.qd_root)
                    for p in base.rglob('*') if p.is_file()}
            print(json.dumps({'url':ready['url'],'root':str(root),'mode':'BROWSER_ONLY'}),flush=True)
            deadline=time.monotonic()+180
            while time.monotonic()<deadline and not (root/'finish').exists():time.sleep(.1)
            after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for base in (s.root,s.qd_root)
                   for p in base.rglob('*') if p.is_file() and p!=root/'finish'}
            assert after==before,'BROWSER_READ_MUTATED_SOURCE_OR_FINANCIAL_EVIDENCE'
            result={'browser_read_unchanged':True,'shutdown':s.r.stop()}
            (root/'acceptance-result.json').write_text(json.dumps(result),encoding='utf-8')
            return
        from urllib.parse import urlsplit
        origin=f"http://127.0.0.1:{urlsplit(ready['url']).port}"
        wrapper=root/'gui-fixture.ps1'
        wrapper.write_text('''$ErrorActionPreference='Stop'
$session=[pscustomobject]@{ url=$env:ATLAS_FIXTURE_URL; token=$env:ATLAS_FIXTURE_TOKEN; id=$env:ATLAS_FIXTURE_HOST }
$session | Add-Member ScriptMethod verify_session { $v=Invoke-RestMethod ($this.url+'/health'); return $v.host_id -ceq $this.id }
$session | Add-Member ScriptMethod request_stop { param($mode)
 $v=Invoke-RestMethod ($this.url+'/_atlas/control/stop') -Method Post -ContentType 'application/json' -Headers @{Origin=$this.url;'X-Atlas-Control'=$this.token} -Body (@{mode=$mode}|ConvertTo-Json -Compress)
 [IO.File]::WriteAllText($env:ATLAS_FIXTURE_RESULT,($v|ConvertTo-Json -Depth 20)); return $v
}
& './scripts/windows/Atlas-Background-Controls.ps1' -AcceptedPaperSession $session
''',encoding='utf-8')
        env={**os.environ,'ATLAS_FIXTURE_URL':origin,'ATLAS_FIXTURE_TOKEN':token,'ATLAS_FIXTURE_HOST':ready['host_id'],
            'ATLAS_FIXTURE_RESULT':str(root/'gui-stop-result.json'),'TEMP':str(root),'TMP':str(root)}
        gui=subprocess.Popen([str(Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'),
            '-NoProfile','-STA','-File',str(wrapper)],cwd=repo,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for base in (s.root,s.qd_root)
                for p in base.rglob('*') if p.is_file() and p.suffix in ('.json','.ack')}
        print(json.dumps({'url':ready['url'],'root':str(root),'gui_pid':gui.pid}),flush=True)
        deadline=time.monotonic()+240
        while gui.poll() is None and time.monotonic()<deadline and not (root/'finish').exists():time.sleep(.1)
        if gui.poll() is None:raise RuntimeError('TEST_GUI_REMAINS_OWNED_CLOSE_REQUIRED')
        out,err=gui.communicate(timeout=2)
        assert gui.returncode==0,(out,err)
        if not (root/'gui-stop-result.json').exists():
            (root/'acceptance-result.json').write_text(json.dumps({'interactive_stop':'NOT_EXECUTED',
                'reason':'TEST_FORM_CLOSED_WITHOUT_INTERACTIVE_STOP','gui_exit':gui.returncode}),encoding='utf-8')
            raise RuntimeError('INTERACTIVE_STOP_NOT_EXECUTED')
        result=json.loads((root/'gui-stop-result.json').read_text(encoding='utf-8-sig'))
        assert result['outcome']['status']=='FLATTENED',result
        assert s.journal.snapshot()['state']['finalized']
        before_read={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in before}
        (root/'acceptance-result.json').write_text(json.dumps({'gui_exit':0,'stop':result,
            'financial_final':s.journal.snapshot()['state']['finalized'],'initial_source_file_count':len(before),
            'final_financial_file_hashes':before_read}),encoding='utf-8')
    finally:
        if s.r.grant is not None and s.r.state!='STOPPED':s.r.stop()
        if h is not None:h.close(ready)
        s.close()


if __name__=='__main__':main()
