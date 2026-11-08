"""Bounded V2 test entry;no new root and no default operational authority."""
import contextlib
import io
import json
import os
import sys
import uuid
from pathlib import Path

os.environ['PYTHONDONTWRITEBYTECODE']='1'
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
sys.dont_write_bytecode=True
sys.path[:0]=[str(Path(__file__).resolve().parents[2]),str(Path(__file__).resolve().parents[2]/'backend'),str(Path(__file__).resolve().parents[2]/'tests')]
from scripts.observation_runtime.native_fixture_budget import NativeFixtureBudget

ROOT=Path(r'D:\Work\Project Atlas\logs\diagnostics\continuation-fixture-77a93d8995474d649d7bda5095d84ab5')


class Capture(io.StringIO):
    def write(self,value):
        room=900000-self.tell()
        if room>0:return super().write(value[:room])
        return len(value)


def main(selection):
    import pytest
    if selection not in ('all','remaining'):raise ValueError('EXPLICIT_BOUNDED_SELECTION_REQUIRED')
    b=NativeFixtureBudget(ROOT)
    if (ROOT/'evidence'/'session-complete.json').exists():raise ValueError('V2_SESSION_ALREADY_CONSUMED')
    if b.anchor['authorization']!='P-ATLAS-NATIVE-CONTINUATION-DISPOSABLE-V2':raise ValueError('WRONG_APPROVAL')
    results=[]
    class Results:
        def pytest_runtest_setup(self,item):
            if b.check()>=1500:pytest.exit('25_MINUTE_TEST_ADMISSION_CLOSED')
        def pytest_runtest_logreport(self,report):
            if report.when=='call' or report.failed:
                results.append({'case':report.nodeid,'phase':report.when,'outcome':report.outcome,'duration':report.duration,'detail':str(report.longrepr)[:4096] if report.failed or report.skipped else ''})
    capture=Capture()
    with contextlib.redirect_stdout(capture),contextlib.redirect_stderr(capture):
        nodes=['tests/test_native_continuation_v2.py'] if selection=='all' else [
            'tests/test_native_continuation_v2.py::test_exact_child_catalog_death_and_fresh_restart[catalog]',
            'tests/test_native_continuation_v2.py::test_exact_child_catalog_death_and_fresh_restart[admitted]',
            'tests/test_native_continuation_v2.py::test_inconsistent_native_current_cut_refuses',
            'tests/test_native_continuation_v2.py::test_concurrent_catalog_requests_select_one_cut',
            'tests/test_native_continuation_v2.py::test_pending_orders_block_switch_without_financial_replay']
        code=pytest.main(nodes+['-q','-x','-p','no:cacheprovider'],plugins=[Results()])
    tag=uuid.uuid4().hex;b.write(ROOT/'evidence'/('run-'+tag+'.txt'),capture.getvalue().encode())
    summary={'exitcode':int(code),'passed':sum(r['outcome']=='passed' for r in results),'failed':sum(r['outcome']=='failed' for r in results),'skipped':sum(r['outcome']=='skipped' for r in results),'cases':results,'usage':b.usage()}
    b.write(ROOT/'evidence'/('run-'+tag+'.json'),json.dumps(summary,indent=2).encode());print(json.dumps({k:v for k,v in summary.items() if k!='cases'}));return int(code)

if __name__=='__main__':raise SystemExit(main(sys.argv[1] if len(sys.argv)==2 else None))
