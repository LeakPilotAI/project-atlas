"""Future exact-owned native-test child;no operational entry or provider access."""
import argparse
import contextlib
import io
import json
import os
import struct
import sys
import sysconfig
import threading
from pathlib import Path

sys.dont_write_bytecode=True
REPO=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(REPO),str(REPO/'backend'),str(REPO/'tests')]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--suite',action='store_true')
    parser.add_argument('--case');parser.add_argument('--lane',choices=('QUALITY_DIPS','HYPERLIQUID'))
    parser.add_argument('--phase',choices=('before_reservation','pending','source','commit','ack'))
    args=parser.parse_args()
    from personal_native_compatibility_fixture import NativeCase, checked_budget
    b=checked_budget()
    timer=threading.Timer(450 if args.suite else 25,lambda:os._exit(97));timer.daemon=True;timer.start()
    print(json.dumps({'ready':os.getpid()}),flush=True)
    if sys.stdin.readline(4)!='GO\n':return 96
    if args.suite:
        import pytest
        results=[]
        class Capture(io.StringIO):
            def write(self,value):
                room=850000-self.tell()
                if room>0:super().write(value[:room])
                return len(value)
        class Results:
            def pytest_runtest_setup(self,item):
                if b.check()>=420:pytest.exit('TEST_ADMISSION_CLOSED_AT_420_SECONDS')
            def pytest_runtest_logreport(self,report):
                if report.when=='call' or report.failed or report.skipped:
                    results.append({'case':report.nodeid,'phase':report.when,'outcome':report.outcome,'detail':str(report.longrepr)[:4096] if report.failed else ''})
        capture=Capture()
        with contextlib.redirect_stdout(capture),contextlib.redirect_stderr(capture):
            code=pytest.main(['tests/test_personal_native_compatibility.py','-q','-x','--tb=short','--capture=sys','-p','no:cacheprovider'],plugins=[Results()])
        b.write(b.root/'evidence'/'pytest-output.txt',capture.getvalue().encode())
        summary={'passed':sum(r['outcome']=='passed' for r in results),'failed':sum(r['outcome']=='failed' for r in results),'skipped':sum(r['outcome']=='skipped' for r in results),'exitcode':int(code),'cases':results}
        summary['expected_cases']=17
        summary['complete']=summary['passed']==17 and summary['failed']==0 and summary['skipped']==0 and int(code)==0
        b.write(b.root/'evidence'/'pytest-results.json',json.dumps(summary,indent=2).encode())
        print(json.dumps({k:v for k,v in summary.items() if k!='cases'}),flush=True)
        return int(code) if summary['complete'] or int(code)!=0 else 1
    if args.case is None or args.lane is None or args.phase is None:raise ValueError('EXACT_CASE_PHASE_REQUIRED')
    case=NativeCase(args.case,args.lane);case.phase=args.phase
    if args.phase=='before_reservation':case.publisher().bootstrap.prepare();os._exit(23)
    case.publisher().publish()
    raise ValueError('REQUESTED_ABRUPT_PHASE_WAS_NOT_REACHED')


def observed_development_layout():
    from scripts.observation_runtime.quality_dips_read_service import observe_self
    return {'schema':'PERSONAL_PYTHON_LAYOUT_V1','launch_executable':sys.executable,
            'native_image':observe_self()['image'],'python_executable':sys.executable,
            'base_executable':sys._base_executable,'prefix':sys.prefix,'base_prefix':sys.base_prefix,
            'stdlib':sysconfig.get_path('stdlib'),'architecture_bits':struct.calcsize('P')*8,
            'version':str(sys.version_info.major)+'.'+str(sys.version_info.minor)}


if __name__=='__main__':raise SystemExit(main())
