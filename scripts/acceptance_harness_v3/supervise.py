import sys
if len(sys.argv)!=4 or sys.argv[1]!='--execute-one-approved-installed-acceptance':
    raise SystemExit('FRESH_EXPLICIT_OPERATOR_APPROVAL_REQUIRED_NO_NATIVE_ACTION')
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from gate import validate_scope
scope_sha256,approved_checkpoint=sys.argv[2:]
validate_scope(scope_sha256,approved_checkpoint)
from pathlib import Path
import ctypes as C
from ctypes import wintypes as W
import _winapi
import msvcrt
import json
import os
import subprocess
import sys
import time

r = Path(r'D:\Work\Project Atlas')
e = Path(__file__).parent
sys.path[:0] = [str(r / 'backend'), str(r)]
from scripts.observation_runtime.disposable_host_owner import observe_pid, observe_handle

class JobLimits(C.Structure):
    _fields_ = [('user',C.c_longlong),('job_user',C.c_longlong),('flags',W.DWORD),
        ('min_working',C.c_size_t),('max_working',C.c_size_t),('active_limit',W.DWORD),
        ('affinity',C.c_size_t),('priority',W.DWORD),('scheduling',W.DWORD)]
class ExtendedLimits(C.Structure):
    _fields_ = [('basic',JobLimits),('io',C.c_ulonglong*6),('process_memory',C.c_size_t),
        ('job_memory',C.c_size_t),('peak_process',C.c_size_t),('peak_job',C.c_size_t)]
class Accounting(C.Structure):
    _fields_ = [('times',C.c_longlong*4),('faults',W.DWORD),('total',W.DWORD),('active',W.DWORD),('terminated',W.DWORD)]

assert not C.windll.shell32.IsUserAnAdmin()
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=r).decode().strip()==approved_checkpoint
assert not (e/'supervisor-result.json').exists() and not (e/'single-use-claim.json').exists()
scopes=[e,Path(r'D:\AtlasRuntime\launchers'),Path(r'D:\AtlasRuntime\support-installations'),Path(r'D:\AtlasRuntime\selection')]
assert all(os.path.isdir(p) for p in scopes[1:])
root_id=e.stat().st_dev,e.stat().st_ino
def account():
    assert (e.stat().st_dev,e.stat().st_ino)==root_id
    entries=logical=0
    for scope in scopes:
        if not os.path.lexists(scope): continue
        for parent,dirs,files in os.walk(scope,followlinks=False):
            for p in [Path(parent),*[Path(parent)/n for n in files]]:
                s=p.lstat()
                if getattr(s,'st_file_attributes',0)&0x400 or p.is_symlink() or p.is_junction():raise ValueError('SCOPE_REPARSE_REFUSAL')
                if p.is_file() and s.st_nlink != 1:
                    if p.parent!=scopes[3] or s.st_nlink!=2:raise ValueError('UNEXPECTED_SCOPE_HARDLINK')
                entries+=1
                if p.is_file():logical+=s.st_size
    return entries,logical,logical+entries*4096

k=C.WinDLL('kernel32',use_last_error=True)
declarations={'CreateJobObjectW':([C.c_void_p,W.LPCWSTR],W.HANDLE),
 'SetInformationJobObject':([W.HANDLE,C.c_int,C.c_void_p,W.DWORD],W.BOOL),
 'AssignProcessToJobObject':([W.HANDLE,W.HANDLE],W.BOOL),'ResumeThread':([W.HANDLE],W.DWORD),
 'QueryInformationJobObject':([W.HANDLE,C.c_int,C.c_void_p,W.DWORD,C.c_void_p],W.BOOL),
 'TerminateJobObject':([W.HANDLE,W.UINT],W.BOOL),'CloseHandle':([W.HANDLE],W.BOOL)}
for name,(args,restype) in declarations.items():getattr(k,name).argtypes,getattr(k,name).restype=args,restype
def check(v):
    if not v:raise C.WinError(C.get_last_error())
job=k.CreateJobObjectW(None,None);check(job)
config=ExtendedLimits();config.basic.flags=0x2000
check(k.SetInformationJobObject(job,9,C.byref(config),C.sizeof(config)))
started=time.perf_counter()
result={'authorization_consumed':True,'base':approved_checkpoint,
 'maximum_seconds':600,'watchdog_seconds':540,'maximum_entries':8192,'maximum_accounted_bytes':67108864,
 'status':'RUNNING','forced_job_cleanup':False,'peak_entries':0,'peak_accounted_bytes':0}
hp=ht=None
try:
    (e/'temp').mkdir(exist_ok=False)
    env=dict(os.environ)
    for name in ('PYTHONPATH','PYTHONHOME'):env.pop(name,None)
    env.update(ATLAS_AUTH_DEADLINE_NS=str(int((started+600)*1e9)),ATLAS_AUTH_SCOPE_SHA256=scope_sha256,ATLAS_AUTH_APPROVED_HEAD=approved_checkpoint,
        ATLAS_AUTH_HELPER_CLAIMS=json.dumps([observe_pid(os.getpid())]),
        PYTHONDONTWRITEBYTECODE='1',TEMP=str(e/'temp'),TMP=str(e/'temp'),
        PSModulePath=r'C:\Windows\System32\WindowsPowerShell\v1.0\Modules',
        PSModuleAnalysisCachePath=str(e/'ps-module-analysis.cache'))
    with open(os.devnull,'rb') as null, (e/'worker-stdout.log').open('xb') as out, (e/'worker-stderr.log').open('xb') as err:
        si=subprocess.STARTUPINFO();si.dwFlags|=subprocess.STARTF_USESTDHANDLES
        si.hStdInput=msvcrt.get_osfhandle(null.fileno());si.hStdOutput=msvcrt.get_osfhandle(out.fileno());si.hStdError=msvcrt.get_osfhandle(err.fileno())
        for h in (si.hStdInput,si.hStdOutput,si.hStdError):os.set_handle_inheritable(h,True)
        worker_python=str(r/'backend/.venv/Scripts/python.exe')
        command=subprocess.list2cmdline([worker_python,'-I','-B',str(e/'worker.py'),'--approved-installed-worker'])
        hp,ht,pid,_=_winapi.CreateProcess(worker_python,command,None,None,True,0x4|0x08000000,env,str(r),si)
        check(k.AssignProcessToJobObject(job,hp))
        claim=observe_pid(pid);assert claim['created']==observe_handle(hp)
        (e/'helper-primary-claim.json').write_text(json.dumps(claim))
        result['worker_claim']=claim
        if k.ResumeThread(ht)==0xffffffff:raise C.WinError(C.get_last_error())
        check(k.CloseHandle(ht));ht=None
        previous=None;offset=0
        while _winapi.WaitForSingleObject(hp,0)==258:
            if (e/'worker-stdout.log').stat().st_size>offset:
                with (e/'worker-stdout.log').open('rb') as stream:stream.seek(offset);data=stream.read();offset+=len(data)
                print(data.decode(errors='replace'),end='',flush=True)
            entries,logical,charged=account()
            result['peak_entries']=max(result['peak_entries'],entries)
            result['peak_accounted_bytes']=max(result['peak_accounted_bytes'],charged)
            if time.perf_counter()-started>=540 or entries>=7800 or charged>=60*1024**2:
                raise ValueError('GLOBAL_TIME_OR_RESOURCE_CLEANUP_RESERVE_REACHED')
            try:
                p=e/'worker-result.json'
                if p.exists():status=json.loads(p.read_bytes()).get('status')
                else:
                    p=e/'native-preflight-progress.json'
                    status='PREFLIGHT_NATIVE_GROUPS_'+str(len(json.loads(p.read_bytes())['checks'])) if p.exists() else 'PREFLIGHT_CLOCK'
                if status!=previous:print(status,flush=True);previous=status
            except (json.JSONDecodeError,PermissionError):pass
            time.sleep(.15)
        result['worker_exit_code']=_winapi.GetExitCodeProcess(hp)
    a=Accounting();check(k.QueryInformationJobObject(job,1,C.byref(a),C.sizeof(a),None))
    result['job_active_after_worker']=a.active
    if a.active:raise ValueError('OWNED_DESCENDANTS_NOT_DRAINED')
    result['status']='COMPLETE' if result['worker_exit_code']==0 else 'REFUSED_PRESERVE_EVIDENCE'
except BaseException as exc:
    result.update(status='REFUSED_PRESERVE_PARTIAL',error=repr(exc),forced_job_cleanup=True)
    check(k.TerminateJobObject(job,1))
    if hp:_winapi.WaitForSingleObject(hp,10000)
finally:
    a=Accounting();check(k.QueryInformationJobObject(job,1,C.byref(a),C.sizeof(a),None));result['job_active_before_close']=a.active
    if ht:check(k.CloseHandle(ht))
    if hp:check(k.CloseHandle(hp))
    check(k.CloseHandle(job));result['job_and_worker_handles_closed']=True
    entries,logical,charged=account();result.update(seconds=time.perf_counter()-started,entries_before_result=entries,logical_bytes_before_result=logical,accounted_bytes_before_result=charged)
    assert result['seconds']<=600 and entries+1<=8192 and charged+16384<67108864
    (e/'supervisor-result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({key:result[key] for key in ('status','seconds','job_active_before_close','forced_job_cleanup','entries_before_result','accounted_bytes_before_result')}),flush=True)
sys.exit(0 if result['status']=='COMPLETE' else 2)
