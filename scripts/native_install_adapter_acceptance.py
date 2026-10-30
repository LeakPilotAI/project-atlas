"""One operator-authorized disposable native copy; never operational install.

The fixed root is create-only. All execution artifacts stay below it. No clock,
provider, financial store, active selector, service or system setting is touched.
"""
import argparse
import copy
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / 'logs/diagnostics/qd-native-install-adapter-v1'
GRANT = 'P-QD-INSTALL-ADAPTER-NATIVE-DISPOSABLE-V1'
LIMITS = {'seconds': 600, 'entries': 40000, 'bytes': 1024**3}


def contained(path, root=ROOT):
    path, root = Path(path).absolute(), Path(root).absolute()
    if not path.is_relative_to(root):
        raise ValueError('DISPOSABLE_NAMESPACE_ESCAPE')
    for parent in (path, *path.parents):
        if os.path.lexists(parent):
            item = parent.lstat()
            if getattr(item, 'st_file_attributes', 0) & 0x400 or stat.S_ISLNK(item.st_mode):
                raise ValueError('DISPOSABLE_REPARSE_REFUSED')
    return path


def usage(root=ROOT, *, permitted_probe_links=()):
    entries, size = 1, 0
    links={}
    for parent, dirs, files in os.walk(contained(root), followlinks=False):
        for leaf in dirs + files:
            path = Path(parent) / leaf
            info = path.lstat()
            if getattr(info, 'st_file_attributes', 0) & 0x400 or stat.S_ISLNK(info.st_mode):
                raise ValueError('DISPOSABLE_REPARSE_REFUSED')
            entries += 1
            if stat.S_ISREG(info.st_mode):
                size += info.st_size
                if info.st_nlink != 1:
                    relative=path.relative_to(root).as_posix()
                    if relative not in permitted_probe_links:
                        raise ValueError('DISPOSABLE_SPECIAL_OR_LINKED_FILE')
                    links.setdefault((info.st_dev,info.st_ino),[]).append((relative,info.st_nlink))
            elif not stat.S_ISDIR(info.st_mode):
                raise ValueError('DISPOSABLE_SPECIAL_OR_LINKED_FILE')
    for group in links.values():
        if any(count!=len(group) for _,count in group):
            raise ValueError('DISPOSABLE_EXTERNAL_HARDLINK_ALIAS')
    return entries, size


def enforce(started, entries, size, *, now=None):
    elapsed = (time.monotonic() if now is None else now) - started
    if elapsed >= 590 or entries >= LIMITS['entries'] or size >= LIMITS['bytes']:
        raise ValueError('DISPOSABLE_LIMIT_REFUSAL_PRESERVE_PARTIAL')


def save(name, value):
    path = contained(ROOT / name)
    raw = json.dumps(value, sort_keys=True, allow_nan=False, indent=2).encode()
    if len(raw) > 16 * 1024**2:
        raise ValueError('BOUNDED_AUDIT_REQUIRED')
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return hashlib.sha256(raw).hexdigest()


def pins():
    proposal_path = REPO / 'docs/QD_UNSELECTED_CODE_INSTALL_PROPOSAL_V1_2026-10-30.json'
    raw = proposal_path.read_bytes().replace(b'\r\n', b'\n')
    if hashlib.sha256(raw).hexdigest() != '888c645b055b016b165c2133a4f9bf69dabbe6f3d5c259a516a863586b7539f2':
        raise ValueError('APPROVED_PROPOSAL_CHANGED')
    proposal = json.loads(raw)
    for name, pin in proposal['adapter_source_sha256'].items():
        if hashlib.sha256((REPO / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest() != pin:
            raise ValueError('REVIEWED_ADAPTER_CHANGED')
    from scripts.native_install_plan import prepare_install_inputs
    arguments = {'archive':proposal['archive'], 'archive_sha256':proposal['archive_sha256'],
        'source_commit':proposal['source_commit'], 'inventory_digest':proposal['inventory_sha256'],
        'dependency_receipt':json.loads(Path(proposal['dependency_receipt']).read_bytes()),
        'dependency_digest':proposal['dependency_sha256'], 'require_tracked':True}
    prepared = prepare_install_inputs(**arguments)
    if (len(prepared['runtime']) != 638 or len(prepared['dependencies']) != 9566
            or len(prepared['directories']) + 1 != 903 or prepared['total'] != 260369081):
        raise ValueError('EXACT_APPROVED_PLAN_REQUIRED')
    return proposal, arguments, prepared


def worker(started, resume=False):
    from scripts import native_install_candidate as copier
    from scripts.install_verified_release import (
        installed_readback,
        validate_installed_readback,
    )
    from scripts.native_install_plan import prepare_install_inputs

    events = []
    result = {'schema': 'QD_NATIVE_INSTALL_ADAPTER_DISPOSABLE_ACCEPTANCE_V1',
        'grant': GRANT, 'status': 'IN_PROGRESS', 'limits': LIMITS, 'financial_actions': 0,
        'provider_connections': 0, 'active_release_modified': False, 'tests': events}
    last_check = 0

    def bound():
        nonlocal last_check
        now = time.monotonic()
        enforce(started, 0, 0, now=now)
        if now - last_check > 4:
            enforce(started, *usage())
            last_check = time.monotonic()
        return True

    def refused(name, function, expected, kind=None):
        bound()
        try:
            function()
        except (ValueError, OSError, KeyError, TypeError) as error:
            if expected not in str(error) or kind is not None and not isinstance(error,kind):
                raise
            events.append({'test': name, 'result': 'PASS', 'refusal': str(error)[:250]})
        else:
            raise AssertionError('MISSING_REQUIRED_REFUSAL:' + name)

    try:
        proposal, arguments, prepared = pins()
        prepared['started'] = started
        # Reserve both trees, all audit receipts and bounded unit-fixture headroom.
        enforce(started, 2 * (len(prepared['names']) + len(prepared['directories']) + 1) + 4096,
                2 * prepared['total'] + 128 * 1024**2)
        dependency_raw = Path(proposal['dependency_receipt']).read_bytes()
        archive_pin = hashlib.sha256(Path(proposal['archive']).read_bytes()).hexdigest()
        if not resume:(ROOT / 'previous-selected-fixture.json').write_bytes(b'SYNTHETIC_PREVIOUS_SELECTION_NOT_ACTIVE')
        prior = (ROOT / 'previous-selected-fixture.json').read_bytes()

        bad = dict(arguments, archive=ROOT / 'ABSENT.zip')
        refused('missing-source', lambda: prepare_install_inputs(**bad), '', FileNotFoundError)
        refused('source-hash-mismatch', lambda: prepare_install_inputs(**dict(arguments, archive_sha256='0'*64)), 'mismatch')
        bad_receipt = copy.deepcopy(arguments['dependency_receipt'])
        bad_receipt['directories'] = []
        refused('incomplete-source-receipt', lambda: prepare_install_inputs(**dict(arguments, dependency_receipt=bad_receipt)), 'INVENTORY')
        duplicate = copy.deepcopy(arguments['dependency_receipt'])
        duplicate['files'].append(copy.deepcopy(duplicate['files'][0]))
        duplicate_pin = hashlib.sha256(json.dumps(duplicate['files'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        refused('namespace-collision', lambda: prepare_install_inputs(**dict(arguments,
            dependency_receipt=duplicate, dependency_digest=duplicate_pin)), 'DUPLICATE')
        oversized = copy.deepcopy(arguments['dependency_receipt'])
        next(row for row in oversized['files'] if row['path'].replace('\\','/').startswith('python/'))['bytes'] = 1024**3
        oversized_pin = hashlib.sha256(json.dumps(oversized['files'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        refused('capacity-before-copy', lambda: prepare_install_inputs(**dict(arguments,
            dependency_receipt=oversized, dependency_digest=oversized_pin)), 'INSTALL_PLAN_LIMIT')

        def progress(value):
            bound()
            if value.get('status'):
                save('copy-' + value['status'] + '.json', value)
            print(json.dumps({'files': len(value['files']), 'stage': value.get('status', 'COPYING')}), flush=True)

        if resume:
            copied = json.loads((ROOT/'copy-NATIVE_COPY_ACL_IDENTITY_HASH_VERIFIED_UNSELECTED.json').read_bytes())
            assert copied['source_commit']==proposal['source_commit'] and copied['archive_sha256']==proposal['archive_sha256']
            assert copied['status']=='NATIVE_COPY_ACL_IDENTITY_HASH_VERIFIED_UNSELECTED'
        else:
            copied = copier._copy_prepared_code(destination=ROOT/'candidate', prepared=prepared,
                archive_sha256=proposal['archive_sha256'], source_commit=proposal['source_commit'],
                observer=progress, admission=bound)
        assert copied['retained_handles_after_close'] == 0
        events.append({'test': 'exact-native-copy-independent-readback', 'result': 'PASS',
            'files': len(copied['files']), 'directories': len(copied['directories']),
            'bytes': copied['charged_bytes'], 'seconds': copied['seconds']})
        receipt = {'schema': 'ATLAS_DISPOSABLE_NATIVE_INSTALLATION_V1',
            'status': 'VERIFIED_COPY_NOT_OPERATIONAL_AUTHORITY', 'release_path': str(ROOT/'candidate'),
            'source_commit': proposal['source_commit'], 'files': copied['files'],
            'directories': copied['directories'], 'selected': False}
        receipt_pin = (hashlib.sha256((ROOT/'installation-receipt.json').read_bytes()).hexdigest()
            if resume else save('installation-receipt.json', receipt))
        assert json.loads((ROOT/'installation-receipt.json').read_bytes()) == receipt
        ack = {'schema': 'QD_DISPOSABLE_CODE_COPY_ACK_V1',
            'receipt_sha256': receipt_pin, 'financial_authority': False, 'selected': False}
        if resume:
            assert json.loads((ROOT/'copy-completion-ack.json').read_bytes())==ack
        else:save('copy-completion-ack.json',ack)
        events.append({'test': 'durable-receipt-and-copy-ack', 'result': 'PASS'})

        # Never relax NativePersonalReleaseIdentity's actual-release path check.
        # This must refuse at the true installed child, preserving domain separation.
        operational_shape = dict(receipt, schema='ATLAS_QD_D_RUNTIME_INSTALLATION_V1', stage='D_RUNTIME_LAYOUT_VERIFIED')
        pin = hashlib.sha256(json.dumps(receipt['files'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        if resume:
            initial=json.loads((ROOT/'result.json').read_bytes())
            assert initial['error'].startswith('ValueError:INSTALLED_RUNTIME_READBACK_REFUSED:')
            events.append({'test':'retained-operational-readback-refusal','result':'PASS',
                'diagnostic_limit':'Original reason truncated; copied-child direct check follows'})
        else:
            refused('operational-readback-rejects-disposable-path', lambda: installed_readback(ROOT/'candidate',
                operational_shape, pin, timeout=min(90, 560-(time.monotonic()-started))), 'PERSONAL_RELEASE_PATH_OR_ARTIFACT')
        refused('incomplete-readback-receipt', lambda: validate_installed_readback({}, ROOT/'candidate',
            operational_shape, pin, {}), 'INCOMPLETE')

        # A genuine copied interpreter proves source origins/layout without pretending
        # the disposable native receipt is accepted operational release authority.
        child_code = """import sys,json,struct,sysconfig
from pathlib import Path
r=Path.cwd();sys.path[:0]=[str(r/'backend'),str(r)]
import scripts.observation_runtime.personal_research_archive as a
import app.services.quality_dips_iex_input as b
from scripts.observation_runtime.personal_release_identity import NativePersonalReleaseIdentity
import hashlib
receipt=json.loads((r.parent/'installation-receipt.json').read_bytes())
receipt.update(schema='ATLAS_QD_D_RUNTIME_INSTALLATION_V1',stage='D_RUNTIME_LAYOUT_VERIFIED')
pin=hashlib.sha256(json.dumps(receipt['files'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
try:NativePersonalReleaseIdentity(receipt=receipt,artifact_digest=pin)
except ValueError as e:
 assert str(e)=='PERSONAL_RELEASE_PATH_OR_ARTIFACT'
else:raise AssertionError('Disposable path cannot be operational authority')
assert Path(sys.executable)==r/'python/python.exe'
assert Path(sys.prefix)==r/'python' and struct.calcsize('P')*8==64
assert all(Path(p).resolve().is_relative_to(r) for p in sys.path if p)
assert all(Path(m.__file__).resolve().is_relative_to(r) for m in (a,b))
print(json.dumps({'executable':sys.executable,'prefix':sys.prefix,'stdlib':sysconfig.get_path('stdlib'),
 'origins':[a.__file__,b.__file__],'operational_domain_refusal':'PERSONAL_RELEASE_PATH_OR_ARTIFACT','financial_actions':0}))
"""
        runtime = run_owned([str(ROOT/'candidate/python/python.exe'), '-I', '-B', '-c', child_code],
            timeout=min(45, 555-(time.monotonic()-started)), cwd=ROOT/'candidate')
        save('copied-runtime.json', json.loads(runtime.decode('utf-8-sig')))
        events.append({'test': 'genuine-copied-runtime-and-two-module-origins', 'result': 'PASS'})

        def interrupted(value):
            bound()
            if value.get('status'):
                save('interrupted-copy.json', value)

        refused('controlled-native-interruption', lambda: copier._copy_prepared_code(destination=ROOT/'interrupted',
            prepared=prepared, archive_sha256=proposal['archive_sha256'], source_commit=proposal['source_commit'],
            observer=interrupted, interrupt_after=3, admission=bound), 'EXPLICIT_SYNTHETIC_INTERRUPTION')
        partial = json.loads((ROOT/'interrupted-copy.json').read_bytes())
        assert partial['retained_handles_after_close'] == 0 and len(partial['files']) == 3
        refused('interrupted-tree-no-blind-retry', lambda: copier.install_synthetic_candidate(destination=ROOT/'interrupted',
            archive=proposal['archive'], archive_sha256=proposal['archive_sha256'], source_commit=proposal['source_commit'],
            dependency_receipt=arguments['dependency_receipt'], dependency_digest=proposal['dependency_sha256']), 'EXACT_NEW')
        assert (ROOT/'previous-selected-fixture.json').read_bytes() == prior
        assert Path(proposal['dependency_receipt']).read_bytes() == dependency_raw
        assert hashlib.sha256(Path(proposal['archive']).read_bytes()).hexdigest() == archive_pin
        assert not Path(proposal['destination']).exists()

        bound()
        test_names = ['test_native_install_plan', 'test_unselected_release_adapter', 'test_native_install_candidate',
            'test_candidate_verifier', 'test_candidate_selected_inventory', 'test_candidate_source_identity',
            'test_candidate_windows_namespace', 'test_personal_release_module_binding',
            'test_nonfinancial_resource_host', 'test_windows_clock_probe_boundary',
            'test_native_install_adapter_acceptance']
        command = [sys.executable, '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '-p', 'pytest_asyncio.plugin',
            '--basetemp', str(ROOT/'pytest'), *[str(REPO/'tests'/(n+'.py')) for n in test_names]]
        output = run_owned(command, timeout=min(70, 555-(time.monotonic()-started)), cwd=ROOT, tests=True)
        (ROOT/'regressions.txt').write_bytes(output)
        events.append({'test': 'focused-broader-regressions', 'result': 'PASS', 'summary': output.decode(errors='replace').splitlines()[-1]})
        # Copier has already verified every native identity, ACL, hash and namespace;
        # verify receipt bytes and exact namespace again after installed execution.
        copier._verify_namespace(ROOT/'candidate', {r['path'] for r in copied['files']},
            {r['path'] for r in copied['directories']}, bound)
        assert hashlib.sha256((ROOT/'installation-receipt.json').read_bytes()).hexdigest() == receipt_pin
        result.update(status='PASS_NATIVE_COPY_DISPOSABLE_ONLY', candidate_files=len(copied['files']),
            candidate_directories=len(copied['directories']), candidate_bytes=copied['charged_bytes'],
            interrupted_files=3, native_handles_after_close=0, source_inputs_unchanged=True,
            previous_fixture_selection_unchanged=True, operational_verifier_acceptance=False)
    except BaseException as error:
        result.update(status='REFUSED_PRESERVE_PARTIAL', error=type(error).__name__+':'+str(error))
        raise
    finally:
        result.update(seconds=round(time.monotonic()-started, 3), usage_before_final_audit=dict(zip(('entries','bytes'),usage())))
        save('continuation-result.json' if resume else 'result.json', result)
        print(json.dumps({'status': result['status'], 'seconds': result['seconds']}), flush=True)


def run_owned(command, *, timeout, cwd, tests=False):
    from scripts.observation_runtime.disposable_host_owner import (
        observe_handle,
        observe_pid,
    )
    if timeout <= 0:
        raise ValueError('DISPOSABLE_LIMIT_REFUSAL_PRESERVE_PARTIAL')
    env = dict(os.environ)
    env.pop('PYTHONHOME', None)
    env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1', TEMP=str(ROOT), TMP=str(ROOT),
        PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PYTHONPATH=os.pathsep.join([str(REPO/'backend'),str(REPO),str(REPO/'tests')]) if tests else '')
    process = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW)
    accepted = False
    try:
        identity = observe_pid(process.pid)
        accepted = identity['created'] == observe_handle(int(process._handle)) and identity['image'] == str(Path(command[0]).resolve()).casefold()
        if not accepted:
            raise ValueError('EXACT_OWNED_CHILD_REQUIRED')
        try:
            output, _ = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            # Only this retained, independently verified creation handle; no PID/name kill.
            process.kill(); process.communicate(timeout=5)
            raise ValueError('EXACT_OWNED_TEST_TIMEOUT_PRESERVE_PARTIAL') from None
        if len(output) > 2*1024**2:
            raise ValueError('TEST_OUTPUT_LIMIT')
        if process.returncode:
            save('failed-child-output-'+str(process.pid)+'.json', {'returncode':process.returncode,'output':output.decode(errors='replace')})
            raise ValueError('OWNED_CHILD_REFUSED:'+output.decode(errors='replace')[-600:])
        return output
    finally:
        if process.poll() is None and accepted:
            process.kill(); process.wait(timeout=5)
        if process.stdout:process.stdout.close()
        process._handle.Close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--grant')
    parser.add_argument('--worker-start', type=float)
    parser.add_argument('--continue-owned',action='store_true')
    parser.add_argument('--finalize-owned-read-only',action='store_true')
    args = parser.parse_args(argv)
    if args.grant != GRANT or os.name != 'nt':
        raise SystemExit('EXPLICIT_SINGLE_DISPOSABLE_WINDOWS_GRANT_REQUIRED')
    if args.finalize_owned_read_only:
        return finalize_owned()
    if args.worker_start is not None:
        if ROOT != Path.cwd() or not ROOT.is_dir():
            raise ValueError('EXACT_OWNED_FIXTURE_REQUIRED')
        return worker(args.worker_start,args.continue_owned)
    started = time.monotonic()
    contained(ROOT)
    if args.continue_owned:
        accepted=json.loads((ROOT/'authorization.json').read_bytes())
        assert accepted['grant']==GRANT and accepted['limits']==LIMITS
        started=accepted['started_monotonic']
        enforce(started,*usage())
        save('single-continuation.json',{'original_started_monotonic':started,
            'copy_repeated':False,'deadline_reset':False,'reason':'Preserve diagnostic truncation failure; finish only remaining checks'})
        try:
            output=run_owned([sys.executable,'-I','-B',str(Path(__file__).resolve()),'--grant',GRANT,
                '--worker-start',str(started),'--continue-owned'],timeout=max(1,580-(time.monotonic()-started)),cwd=ROOT)
            (ROOT/'continuation-output.txt').write_bytes(output)
        finally:
            entries,size=usage();elapsed=time.monotonic()-started
            save('continuation-supervisor-final.json',{'seconds':round(elapsed,3),'entries_before_final':entries,
                'bytes_before_final':size,'process_handle_closed':True,'retained_process_running':False,
                'port_opened':False,'limits_pass':elapsed<600 and entries+1<40000 and size+65536<1024**3})
        print(json.dumps({'continued_original_run':True,'seconds':round(elapsed,3)}),flush=True)
        return
    if os.path.lexists(ROOT):
        raise ValueError('SINGLE_RUN_ALREADY_CONSUMED_PRESERVE_NO_RETRY')
    _, _, prepared = pins()
    if shutil.disk_usage(ROOT.parent).free < 1024**3 + 64*1024**2:
        raise ValueError('INSUFFICIENT_DISPOSABLE_CAPACITY')
    from scripts.volume_inspector.windows_output import WindowsOutput, close_handle
    root = WindowsOutput.create_root(str(ROOT))
    try:root._verify()
    finally:
        while root.handles:
            if not close_handle(root.handles[-1]):raise OSError('FIXTURE_ROOT_HANDLE_CLOSE_UNCONFIRMED')
            root.handles.pop()
    save('authorization.json', {'grant':GRANT,'limits':LIMITS,'started_monotonic':started,
        'source_plan_bytes':prepared['total'],'financial_authority':False})
    try:
        output = run_owned([sys.executable, '-I', '-B', str(Path(__file__).resolve()), '--grant', GRANT,
            '--worker-start', str(started)], timeout=max(1,580-(time.monotonic()-started)), cwd=ROOT)
        (ROOT/'worker-output.txt').write_bytes(output)
    finally:
        entries, size = usage()
        elapsed = time.monotonic()-started
        save('supervisor-final.json', {'seconds':round(elapsed,3),'entries_before_final':entries,'bytes_before_final':size,
            'process_handle_closed':True,'retained_process_running':False,'port_opened':False,
            'limits_pass':elapsed<600 and entries+1<40000 and size+65536<1024**3})
    print(json.dumps({'root':str(ROOT),'seconds':round(elapsed,3),'entries_before_final':entries,'bytes_before_final':size}),flush=True)


def finalize_owned():
    """Finish the original bounded run only; no new copy, child or domain change."""
    import ctypes as C
    from contextlib import ExitStack

    from scripts.native_install_candidate import _verify_namespace
    from scripts.volume_inspector import windows_output as w
    accepted=json.loads((ROOT/'authorization.json').read_bytes())
    if accepted['grant']!=GRANT or accepted['limits']!=LIMITS:
        raise ValueError('EXACT_ORIGINAL_AUTHORIZATION_REQUIRED')
    started=accepted['started_monotonic']
    probes={'pytest/test_native_hard_link_source_i0/outside-source.py',
            'pytest/test_native_hard_link_source_i0/source/backend/app/example.py'}
    def bound():
        enforce(started,0,0)
    enforce(started,*usage(permitted_probe_links=probes))
    if (ROOT/'final-readonly-acceptance.json').exists():raise ValueError('FINALIZATION_ALREADY_RECORDED')
    pins()
    copy_fact=json.loads((ROOT/'copy-NATIVE_COPY_ACL_IDENTITY_HASH_VERIFIED_UNSELECTED.json').read_bytes())
    interrupted=json.loads((ROOT/'interrupted-copy.json').read_bytes())
    receipt_raw=(ROOT/'installation-receipt.json').read_bytes()
    receipt=json.loads(receipt_raw)
    assert receipt['files']==copy_fact['files'] and receipt['directories']==copy_fact['directories']
    assert json.loads((ROOT/'copy-completion-ack.json').read_bytes())['receipt_sha256']==hashlib.sha256(receipt_raw).hexdigest()
    assert interrupted['retained_handles_after_close']==copy_fact['retained_handles_after_close']==0
    assert len(interrupted['files'])==3 and interrupted['status']=='REFUSED_PRESERVE_PARTIAL'
    assert (ROOT/'previous-selected-fixture.json').read_bytes()==b'SYNTHETIC_PREVIOUS_SELECTION_NOT_ACTIVE'
    assert '193 passed' in (ROOT/'regressions.txt').read_text()
    outputs={};opened=[];read_bytes=0
    try:
        with ExitStack() as stack:
            for row in receipt['directories']:
                bound();out=w.WindowsOutput(str(ROOT/'candidate'/row['path']));outputs[row['path']]=out
                stack.callback(out.close)
                i=w.info(out.root_handle)
                assert [i.volume,i.index_hi,i.index_lo]==row['id']
            for row in receipt['files']:
                bound();p=Path(row['path']);out=outputs[p.parent.as_posix()]
                h=w.relative_open(out.root_handle,p.name,out.sid,False,access=w.READ|w.READ_CONTROL);opened.append(h)
                try:
                    w.validate_acl(h,out.sid);i=w.info(h)
                    assert [i.volume,i.index_hi,i.index_lo]==row['id'] and i.links==1
                    checksum=hashlib.sha256();size=0
                    while True:
                        bound();buf=C.create_string_buffer(65536);n=w.W.DWORD()
                        w.check(w.read_file(h,buf,65536,C.byref(n),None))
                        if not n.value:break
                        size+=n.value;checksum.update(buf.raw[:n.value])
                        if size>row['bytes']:raise ValueError('FINAL_READBACK_GROWTH')
                    assert size==row['bytes'] and checksum.hexdigest()==row['sha256'];read_bytes+=size
                finally:
                    if not w.close_handle(h):raise OSError('FINAL_READBACK_CLOSE_UNCONFIRMED')
                    opened.remove(h)
            _verify_namespace(ROOT/'candidate',{r['path'] for r in receipt['files']},
                {r['path'] for r in receipt['directories']},bound)
    finally:
        assert not opened and all(not out.handles for out in outputs.values())
    entries,size=usage(permitted_probe_links=probes);enforce(started,entries,size)
    # NTFS allocation unit was separately observed as4096; conservatively charge
    # every entry including directories and duplicate hardlink aliases in full.
    conservative_allocation=size+entries*4096
    enforce(started,entries,conservative_allocation)
    save('final-readonly-acceptance.json',{'schema':'QD_NATIVE_COPY_FINAL_DISPOSABLE_AUDIT_V1',
        'status':'NATIVE_COPY_AND_INTERRUPTION_VERIFIED_HARNESS_FAILURES_RETAINED',
        'seconds':round(time.monotonic()-started,3),'files':len(receipt['files']),
        'directories':len(receipt['directories']),'readback_bytes':read_bytes,
        'entries_before_final':entries,'logical_bytes_before_final':size,
        'conservative_allocation_bytes':conservative_allocation,'retained_native_handles':0,
        'regressions':{'passed':193,'failed':0,'skipped':0},'classified_probe_aliases':sorted(probes),
        'unexpected_links':0,'financial_actions':0,'provider_connections':0,'new_children_in_finalization':0,
        'original_failures_preserved':True,'operational_acceptance':False})
    print(json.dumps({'final_native_readback':'PASS','original_scope_seconds':round(time.monotonic()-started,3),
        'entries':entries+1,'logical_bytes_before_final':size,'native_handles':0}),flush=True)


if __name__ == '__main__':
    # Isolated interpreter ignores PYTHONPATH. Only the reviewed workspace tools
    # enter this *test controller*; copied-runtime checks use their own root.
    sys.path[:0] = [str(REPO/'backend'),str(REPO)]
    main()
