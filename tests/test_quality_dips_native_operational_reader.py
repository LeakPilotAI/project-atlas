"""Synthetic operational-schema bytes in confined roots, never real enrollment."""
import copy
import importlib.util
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
from datetime import datetime
from http.client import HTTPConnection
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.investment import quality_dips_operational_contract as c
from app.investment.quality_dips_operational_replay import (
    history,
    initial,
    replay,
    transition,
)
from test_quality_dips_operational_contract import fixture as schema_fixture

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


reader_module = module("op_native_reader", "scripts/volume_inspector/operational_financial_read.py")
service_module = module("op_native_service", "scripts/observation_runtime/quality_dips_read_service.py")
bridge_module = module("op_native_bridge", "scripts/observation_runtime/quality_dips_windows_bridge.py")


def build(path, damage=None, count=3, event_times=None, observed=None):
    allowed = Path(os.environ["ATLAS_READ_ACCEPTANCE_ROOT"])
    assert allowed.parent == ROOT / "logs/diagnostics" and allowed.name.startswith("qd-read-integration-")
    assert path.is_relative_to(allowed)
    path.mkdir(parents=True, exist_ok=True)
    assert all(not p.is_symlink() and not p.is_junction() for p in [path, *path.parents])
    x = schema_fixture()
    e, b = x.e, x.b
    outputs = {}
    for role in c.ROLES:
        output = reader_module.s.w.WindowsOutput.create_root(str(path / role))
        outputs[role] = output
        e["resources"][role].update(root_path=str(path / role), native_root=reader_module.s.native.file_identity(output.root_handle))
    n = SimpleNamespace(path=path, e=e, b=b, now=observed or int(datetime.fromisoformat("2026-10-23T12:00:00+00:00").timestamp()), available=True)
    def publish(role, name, value):
        bound = outputs[role].write_bound(name, c.body(value).encode())
        return {"schema": "QD_OP_FILE_BINDING_V1", "native_id": bound["id"], "sha256": bound["sha256"], "record_schema": value["schema"]}
    records = []
    try:
        inception = publish("source", "inception.json", e["account"])
        source = {"schema": "QD_OP_SOURCE_PIN_V1", "resource_id": "source", "native_root": e["resources"]["source"]["native_root"],
                      "revision": count, "inception": inception, "records": [], "head_digest": inception["sha256"]}
        previous = inception
        state = initial()
        times = [int(datetime.fromisoformat(t).timestamp()) for t in event_times or
                 ("2026-10-20T19:00:00+00:00", "2026-10-21T15:00:00+00:00", "2026-10-22T15:00:00+00:00")]
        for i in range(count):
            command = {"schema": "QD_OP_COMMAND_V1", "epoch": e["account"]["epoch"], "operation_id": "synthetic-op-"+str(i),
                "kind": "ENTRY" if i == 0 else "EXIT", "expected_source_revision": i, "timestamp": times[i], "manual": True,
                "quote": {"symbol": "MSFT", "price": ("100", "110", "120")[i], "observed_at": times[i], "source_id": "SYNTHETIC_NOT_MARKET"},
                "quantity": ("1", "0.4", "0.6")[i]}
            if i == 0:
                command.update(symbol="MSFT", side="LONG", risk_price=None, origin_ref="synthetic-rank-1",
                    eligibility={"schema": "QD_OP_EXECUTION_EVIDENCE_V1", "instrument_id": "SYNTHETIC-MSFT", "symbol": "MSFT",
                        "asset_class": "STOCK", "fractional_supported": True, "ranked_at": times[i], "ranking_revision": 1, "execution_eligible": True})
            else:
                command.update(position_id=next(iter(state["positions"])), expected_position_revision=i)
            state, receipt = transition(e, state, command)
            commit = {"schema": "QD_OP_COMMIT_V1", "revision": i+1, "event_digest": c.digest([previous, command, receipt])}
            record = {"schema": "QD_OP_FINANCIAL_RECORD_V1", "enrollment_digest": c.digest(e), "revision": i+1,
                "operation_id": command["operation_id"], "predecessor": previous, "command": command, "receipt": receipt, "commit": commit,
                "ack": {"schema": "QD_OP_ACK_V1", "commit_digest": c.digest(commit), "projection_state_digest": c.digest(state), "status": "ACKNOWLEDGED"}}
            if damage in ("ack", "predecessor", "test_schema", "receipt", "duplicate") and i == count-1:
                if damage == "ack": record["ack"] = None
                if damage == "predecessor": record["predecessor"] = inception
                if damage == "test_schema": record["schema"] = "FS2_RECORD_V1"
                if damage == "receipt": record["receipt"]["state_digest"] = "f"*64
                if damage == "duplicate": record["command"]["operation_id"] = "synthetic-op-0"
            previous = publish("source", f"{i+1:04d}-record.json", record)
            source["records"].append(previous)
            source["head_digest"] = previous["sha256"]
            records.append(record)
        # Build expected reports from untampered fixture snapshots, not native acceptance.
        if damage in ("ack", "predecessor", "test_schema", "receipt", "duplicate"):
            snapshots = [initial()] * (count+1)
        else:
            _, snapshots = replay(e, {"revision": count, "source": source}, records, n.now)
        projection = {"schema": "QD_OP_PROJECTION_DOCUMENT_V1", "enrollment_digest": c.digest(e), "source_pin_digest": c.digest(source), "revision": count, "state": state}
        report = {"schema": "QD_OP_REPORT_DOCUMENT_V2", "enrollment_digest": c.digest(e), "source_pin_digest": c.digest(source),
                      "revision": count, "status": "INCOMPLETE", "timezone": "America/New_York", "cutoff": n.now,
                      "history": history(records, snapshots, n.now, "America/New_York")}
        if damage == "financial": projection["state"]["cash"] = "9999"
        if damage == "report": report["history"][0]["opening_cash"] = "8888"
        if damage == "history_omission": report["history"].pop(0)
        if damage == "false_complete": report["status"] = "COMPLETE"
        current = {"schema": "QD_OP_CURRENT_V1", "enrollment_digest": c.digest(e), "generation": 1, "revision": count,
                       "acknowledged_revision": count, "status": "ACKNOWLEDGED", "source": source}
        for role, doc in (("projection", projection), ("report", report)):
            current[role] = {"schema": "QD_OP_"+role.upper()+"_PIN_"+("V2" if role == "report" else "V1"),
                "resource_id": role, "native_root": e["resources"][role]["native_root"], "revision": count,
                "source_pin_digest": c.digest(source), "record": publish(role, role+".json", doc)}
        b["current"] = current
        for key in ("clock", "authority", "session"):
            b[key]["issued_at"], b[key]["expires_at"] = n.now, n.now+30
        n.process = service_module.observe_self()
        b["session"]["process"] = {"schema":"QD_OP_PROCESS_ID_V1", **n.process}
        b["session"]["enrollment_digest"] = c.digest(e)
        b["authority"].update(enrollment_digest=c.digest(e), current_digest=c.digest(current), clock_digest=c.digest(b["clock"]), session_digest=c.digest(b["session"]))
        n.expected = copy.deepcopy(b)
        @contextmanager
        def lease(enrollment, now):
            assert c.body(enrollment) == c.body(e)
            yield SimpleNamespace(snapshot=copy.deepcopy(n.expected), check=lambda value, t: n.available and c.body(value) == c.body(n.expected))
        n.authority = SimpleNamespace(lease=lease)
        n.port = reader_module.NativeOperationalReadPort(authority=n.authority, clock=lambda:n.now,
            observer=service_module.observe_self, host_identity=lambda:n.expected["session"]["host_id"])
        n.cap = c.OperationalReadCapability(enrollment=e, authority=n.authority, clock=lambda:n.now, port=n.port,
            process_identity=b["session"]["process"], host_id=b["session"]["host_id"])
        n.records, n.state = records, state
        return n
    finally:
        for output in outputs.values(): output.close()


@pytest.fixture
def native(tmp_path):
    return build(tmp_path)


def read(n): return n.cap.read_committed(n.e["account"]["account_id"], n.e["account"]["epoch"])


def composition(n):
    @contextmanager
    def accepted(context, now):
        assert context["schema"] in ("QD_OP_READ_SERVICE_CONTEXT_V1", "QD_OP_BRIDGE_CONTEXT_V1")
        assert context["account_id"] == n.e["account"]["account_id"] and context["epoch"] == n.e["account"]["epoch"]
        assert context["process"] in (n.process, {"schema":"QD_OP_PROCESS_ID_V1", **n.process})
        yield SimpleNamespace(check=lambda value,t: n.available and value == context)
    n.acceptance = SimpleNamespace(lease=accepted)
    result=service_module.ReadComposition(account_id=n.e["account"]["account_id"], epoch=n.e["account"]["epoch"],
        enrollment=n.e, custody=n.authority, clock=lambda:n.now, resources=n.port, acceptance=n.acceptance, observer=service_module.observe_self)
    n.expected["session"]["host_id"] = result.host_id
    n.expected["authority"]["session_digest"] = c.digest(n.expected["session"])
    return result


def hashes(path):
    return {str(p.relative_to(path)): c.digest(p.read_bytes().hex()) for p in path.rglob('*') if p.is_file()}


def test_native_replay_partial_full_and_no_read_writes(native, monkeypatch):
    n=native;before=hashes(n.path)
    monkeypatch.setattr(reader_module.s.w.WindowsOutput,"write_bound",lambda *a:pytest.fail("read wrote"))
    monkeypatch.setattr(reader_module.s.w.WindowsOutput,"create_root",lambda *a:pytest.fail("read provisioned"))
    result=read(n)
    assert result["state"]["cash"] == "1015.92000" or c.number(result["state"]["cash"]) == c.number("1015.92")
    assert c.number(result["state"]["net"]) == c.number("15.92")
    assert result["report_status"] == "INCOMPLETE" and result["report"]["history"][0]["open_positions"]
    assert hashes(n.path) == before
    assert n.port.verify_operational(n.e,n.expected["current"],n.port.read_operational(n.e,n.expected["current"])) is True


@pytest.mark.parametrize("count",[0,1,2])
def test_overnight_remaining_and_empty_accounts(tmp_path,count):
    n=build(tmp_path,count=count)
    result=read(n)
    if count:
        remaining=next(iter(result["state"]["positions"].values()))["remaining"]
        assert c.number(remaining) == c.number("1" if count==1 else "0.6")
    else: assert result["state"]["positions"] == {}


@pytest.mark.parametrize("damage",["ack","predecessor","test_schema","receipt","duplicate","financial","report","history_omission","false_complete"])
def test_coherently_pinned_malformed_or_incomplete_source_refuses(tmp_path,damage):
    n=build(tmp_path,damage=damage);before=hashes(n.path)
    with pytest.raises((ValueError,KeyError,TypeError)):read(n)
    assert hashes(n.path)==before


@pytest.mark.parametrize("damage",["stale","revoked","rollback","foreign_root","missing_record","extra_tail","hardlink"])
def test_custody_and_namespace_refusal(native,damage):
    n=native
    if damage=="stale":n.now+=31
    if damage=="revoked":n.available=False
    if damage=="rollback":
        wrong=copy.deepcopy(n.expected["current"]);wrong["generation"]=2
        with pytest.raises(ValueError):n.port.read_operational(n.e,wrong)
        return
    if damage=="foreign_root":n.e["resources"]["source"]["native_root"]=[0,0,0]
    if damage=="missing_record":(n.path/'source/0003-record.json').rename(n.path/'missing.json')
    if damage=="extra_tail":(n.path/'source/0004-record.json').write_text('{}')
    if damage=="hardlink":os.link(n.path/'source/inception.json', n.path/'linked-account.json')
    with pytest.raises((ValueError,OSError,AssertionError)):read(n)


def test_identity_checked_before_readfile(native,monkeypatch):
    n=native
    with reader_module.s.w.WindowsOutput(str(n.path/'source')) as out:
        pin=copy.deepcopy(n.expected["current"]["source"]["inception"]);pin["native_id"]=[1,1,1]
        monkeypatch.setattr(reader_module.s.w,"read_file",lambda *a:pytest.fail('read before identity'))
        with pytest.raises((ValueError,OSError)):n.port._read(out,'inception.json',pin,'QD_OP_ACCOUNT_V1')


def test_concurrent_read_and_projection_substitution(native):
    n=native
    with ThreadPoolExecutor(max_workers=3) as pool:
        assert all(v["source_revision"]==3 for v in pool.map(lambda _:read(n),range(6)))
    docs=n.port.read_operational(n.e,n.expected["current"]);docs['projection']['state']['cash']='9999'
    assert n.port.verify_operational(n.e,n.expected["current"],docs) is False


def test_real_http_operational_records_and_owned_shutdown(native):
    n=native;before=hashes(n.path)
    service=composition(n);host=service_module.OwnedReadHost(service);ready=host.open_read_only_session()
    port=host.listener.getsockname()[1]
    try:
        with closing(HTTPConnection('127.0.0.1',port,timeout=5)) as conn:
            conn.request('GET',service_module.SELECTED);r=conn.getresponse();view=json.loads(r.read())
            assert r.status==200 and view['status']=='ACKNOWLEDGED' and c.number(view['cash'])==c.number('1015.92')
            # Exercise the actual unchanged frontend validator against real HTTP.
            js = "const fs=require('fs');const api=require(process.argv[1]);api.validate(JSON.parse(fs.readFileSync(0,'utf8')));console.log('VALID_ORIGINAL_UI');"
            checked = subprocess.run(['node','-e',js,str(ROOT/'backend/app/static/quality_dips_selected_paper.js')],
                input=json.dumps(view),text=True,capture_output=True,check=False)
            assert checked.returncode == 0, checked.stderr
            assert 'VALID_ORIGINAL_UI' in checked.stdout
            assert view['report']['view_only'] is True and view['report']['operational_source_schema']=='QD_OP_REPORT_DOCUMENT_V2'
            conn.request('POST',service_module.SELECTED+'/commands',body='{}');r=conn.getresponse();r.read();assert r.status==403
            conn.request('GET','/api/investments/quality-dips');r=conn.getresponse();r.read();assert r.status==404
        assert host.verify_read_only_session(ready) is True
        wrong=copy.deepcopy(ready);wrong['process']['pid']+=1
        with pytest.raises(ValueError):host.close_read_only_session(wrong)
        assert host.thread.is_alive()
    finally:assert host.close_read_only_session(ready) is True
    assert hashes(n.path)==before
    with closing(__import__('socket').socket()) as probe:assert probe.connect_ex(('127.0.0.1',port))!=0
    fresh=composition(n);second=service_module.OwnedReadHost(fresh);r=second.open_read_only_session()
    assert r['host_id']!=ready['host_id'];assert second.close_read_only_session(r) is True


@pytest.mark.parametrize("damage", ["ok", "pid", "creation", "image", "authority", "host", "response_duplicate", "response_escaped", "response_version", "response_sequence"])
def test_real_stdio_bridge_with_powershell_and_no_browser(tmp_path, damage):
    # Only this retained test-owned child receives synthetic dependencies.
    program=tmp_path/'child.py'
    program.write_text('''import json,sys\nfrom pathlib import Path\nfrom test_quality_dips_native_operational_reader import build,composition,service_module,bridge_module\nn=build(Path(sys.argv[1]));s=composition(n);h=service_module.OwnedReadHost(s)\ncontext={"schema":"QD_OP_BRIDGE_CONTEXT_V1","host_id":s.host_id,"process":s.identity,"account_id":s.account,"epoch":s.epoch,"enrollment_digest":__import__("app.services.paper_financial_replay",fromlist=["digest"]).digest(s.enrollment)}\nprint(json.dumps(context,sort_keys=True),flush=True)\nclass FaultWriter:\n def write(self,raw):\n  mode=sys.argv[2]\n  if mode=="response_duplicate":raw=raw.rstrip()[:-1]+',"status":"OK"}\\n'\n  if mode=="response_escaped":raw=raw[:-1].rstrip()[:-1]+',"\\\\u0073tatus":"OK"}\\n'\n  if mode=="response_version":raw=raw.replace("QD_OP_BRIDGE_RESPONSE_V1","QD_OP_BRIDGE_RESPONSE_V99")\n  if mode=="response_sequence":raw=raw.replace('"sequence":1','"sequence":1.0')\n  sys.stdout.write(raw)\n def flush(self):sys.stdout.flush()\nbridge_module.serve_bridge(h,control_authority=n.acceptance,clock=lambda:n.now,reader=sys.stdin,writer=FaultWriter())\n''')
    script=tmp_path/'bridge.ps1'
    script.write_text('''param($Repo,$Program,$Store,$Executable,$Damage)\n$ErrorActionPreference='Stop'\nImport-Module (Join-Path $Repo 'scripts/windows/Atlas-SelectedPaper-Bridge.psm1') -Force\n$p=New-Object System.Diagnostics.Process\n$p.StartInfo.FileName=$Executable\n$p.StartInfo.Arguments='"'+$Program+'" "'+$Store+'" '+$Damage\n$p.StartInfo.UseShellExecute=$false;$p.StartInfo.CreateNoWindow=$true\n$p.StartInfo.RedirectStandardInput=$true;$p.StartInfo.RedirectStandardOutput=$true\n[void]$p.Start()\ntry {\n$pending=$p.StandardOutput.ReadLineAsync();if(-not $pending.Wait(15000)){throw 'fixture context timeout'}\n$e=$pending.Result|ConvertFrom-Json\nWrite-Output ('OWNED='+$p.Id+','+$p.StartTime.ToUniversalTime().ToFileTimeUtc()+','+$p.MainModule.FileName+' CHILD='+($e.process|ConvertTo-Json -Compress))\n$authorize={param($c) $c.account_id -ceq 'synthetic-account' -and $c.epoch -ceq 'synthetic-epoch'}\nif($Damage -eq 'pid'){$e.process.pid++}\nif($Damage -eq 'creation'){$e.process.creation_filetime++}\nif($Damage -eq 'image'){$e.process.image='foreign.exe'}\nif($Damage -eq 'host'){$e.host_id='bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'}\nif($Damage -eq 'authority'){$authorize={param($c) $false}}\n$bridge=New-AtlasSelectedReadBridge -OwnedProcess $p -ExpectedContext $e -Authorize $authorize\nif($Damage -ne 'ok'){try{$bridge.open_read_only_session();throw 'DID_NOT_REFUSE'}catch{if($_.Exception.Message -match 'DID_NOT_REFUSE'){throw}};if($Damage -like 'response_*'){try{$bridge.open_read_only_session();throw 'DID_NOT_REFUSE'}catch{if($_.Exception.Message -match 'DID_NOT_REFUSE'){throw}};if(-not $bridge.close_read_only_session($null)){throw 'uncertain owned close failed'}};Write-Output 'BRIDGE_EXPECTED_REFUSAL';return}\n$ready=$bridge.open_read_only_session()\nif(-not $bridge.verify_read_only_session($ready)){throw 'verify failed'}\nImport-Module (Join-Path $Repo 'scripts/windows/Atlas-SelectedPaper-ReadOnly.psm1') -Force\n& (Get-Module Atlas-SelectedPaper-ReadOnly) {function script:Start-Process {param($FilePath,$ErrorAction) $script:fixtureBrowserUrl=$FilePath}}\nOpen-AtlasSelectedPaperDashboard -Root $Repo -AcceptedBridge $bridge\n$opened=& (Get-Module Atlas-SelectedPaper-ReadOnly) {$script:fixtureBrowserUrl}\nif($opened -cne $ready.url){throw 'browser opened before verified readiness'}\n$again=$bridge.open_read_only_session();if($again.host_id -cne $ready.host_id){throw 'duplicate host'}\nClose-AtlasSelectedPaperDashboard\nif(-not $bridge.close_read_only_session($ready)){throw 'repeated close failed'}\nWrite-Output 'BRIDGE_FIXTURE_PASS'\n} finally {if(-not $p.HasExited){$p.StandardInput.Close();if(-not $p.WaitForExit(12000)){throw 'fixture remains owned; no kill'}}}\n''')
    env=dict(os.environ);env['PYTHONPATH']=str(ROOT/'backend')+';'+str(ROOT/'tests')+';'+str(ROOT/'backend/.venv/Lib/site-packages')
    env['PSMODULEPATH']=str(Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/Modules')
    result=subprocess.run(['powershell.exe','-NoProfile','-File',str(script),str(ROOT),str(program),str(tmp_path/'store'),sys._base_executable,damage],env=env,capture_output=True,text=True,timeout=65,check=False)
    assert result.returncode==0,result.stdout+'\n'+result.stderr
    assert ('BRIDGE_FIXTURE_PASS' if damage == 'ok' else 'BRIDGE_EXPECTED_REFUSAL') in result.stdout


@pytest.mark.parametrize('damage',['clock','custody','process'])
def test_native_continuity_loss_during_read(native,monkeypatch,damage):
    n=native;original=reader_module.s.read_bound
    def changed(*args,**kwargs):
        result=original(*args,**kwargs)
        if damage=='clock':n.now+=31
        if damage=='custody':n.available=False
        if damage=='process':n.port.observer=lambda:{**n.process,'pid':n.process['pid']+1}
        return result
    monkeypatch.setattr(reader_module.s,'read_bound',changed)
    with pytest.raises(ValueError):n.port.read_operational(n.e,n.expected['current'])


def test_native_report_dst_boundary(tmp_path):
    observed=int(datetime.fromisoformat('2026-11-02T12:00:00+00:00').timestamp())
    n=build(tmp_path,event_times=('2026-10-31T23:50:00-04:00','2026-11-01T01:30:00-04:00','2026-11-01T01:30:00-05:00'),observed=observed)
    rows=read(n)['report']['history']
    day=next(r for r in rows if r['date']=='2026-11-01')
    assert day['end_exclusive']-day['start']==25*3600
    assert c.number(day['realized']['net'])==c.number('15.92')
    assert rows[0]['open_positions'] and not day['open_positions']


def test_policy_math_ignores_ambient_decimal_precision(native):
    from decimal import localcontext
    command=copy.deepcopy(native.records[0]['command']);command['quote']['price']='100.00001'
    with localcontext() as ctx:
        ctx.prec=3
        with pytest.raises(ValueError,match='ENTRY_POLICY'):transition(native.e,initial(),command)


@pytest.mark.parametrize('damage',['version','duplicate','sequence','process','unknown_action'])
def test_stdio_malformed_control_never_starts_host(native,damage):
    from io import StringIO
    n=native;s=composition(n);host=service_module.OwnedReadHost(s)
    request={'schema':'QD_OP_BRIDGE_COMMAND_V1','sequence':1,'host_id':s.host_id,'process':s.identity,'action':'OPEN','ready':None}
    if damage=='version':request['schema']='QD_OP_BRIDGE_COMMAND_V99'
    if damage=='sequence':request['sequence']=True
    if damage=='process':request['process']={**s.identity,'pid':s.identity['pid']+1}
    if damage=='unknown_action':request['action']='WRITE'
    raw=c.body(request)
    if damage=='duplicate':raw=raw[:-1]+',"sequence":1}'
    out=StringIO()
    bridge_module.serve_bridge(host,control_authority=n.acceptance,clock=lambda:n.now,reader=StringIO(raw+'\n'),writer=out)
    assert json.loads(out.getvalue())['status']=='REFUSED' and host.listener is None


def test_native_true_symlink_is_refused_or_not_executed(native):
    n=native;alias=n.path/'source-link'
    try:os.symlink(n.path/'source',alias,target_is_directory=True)
    except OSError as error:
        if error.winerror==1314:pytest.skip('NOT EXECUTED: true-symlink privilege unavailable')
        raise
    with pytest.raises((OSError,ValueError)):reader_module.s.w.WindowsOutput(str(alias))


def test_native_junction_is_refused(native):
    n=native;alias=n.path/'source-junction'
    result=subprocess.run(['cmd.exe','/c','mklink','/J',str(alias),str(n.path/'source')],capture_output=True,check=False)
    assert result.returncode==0,result.stderr
    with pytest.raises((OSError,ValueError)):reader_module.s.w.WindowsOutput(str(alias))


@pytest.mark.parametrize('symbol,asset',[('AAPL','STOCK'),('SPY','ETF'),('QQQ','ETF')])
def test_native_arithmetic_policy_has_no_msft_allowlist(native,symbol,asset):
    command=copy.deepcopy(native.records[0]['command'])
    command['symbol']=command['quote']['symbol']=command['eligibility']['symbol']=symbol
    command['eligibility']['asset_class']=asset
    command['eligibility']['instrument_id']='SYNTHETIC-'+symbol
    state,_=transition(native.e,initial(),command)
    assert next(iter(state['positions'].values()))['symbol']==symbol


@pytest.mark.parametrize('damage',['unsupported','stale_rank','fractional'])
def test_operational_read_replay_enforces_instrument_evidence(native,damage):
    command=copy.deepcopy(native.records[0]['command'])
    if damage=='unsupported':command['eligibility']['asset_class']='CRYPTO'
    if damage=='stale_rank':command['eligibility']['ranked_at']-=31
    if damage=='fractional':command['eligibility']['fractional_supported']=False;command['quantity']='0.5'
    with pytest.raises(ValueError):transition(native.e,initial(),command)


def test_operational_predecessor_identity_types_are_not_coerced(native):
    records=copy.deepcopy(native.records)
    records[-1]['predecessor']['native_id'][1]=float(records[-1]['predecessor']['native_id'][1])
    with pytest.raises(ValueError,match='LINEAGE'):
        replay(native.e,native.expected['current'],records,native.now)
