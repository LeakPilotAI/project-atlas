"""Exact retained test-child handles;no process discovery or name/port termination."""
import ctypes as C
import os
import subprocess
import sys
import time
from ctypes import wintypes as W
from pathlib import Path

from app.services.paper_financial_replay import body
from native_continuation_v2_fixture import ROOT

from scripts.observation_runtime.native_fixture_budget import NativeFixtureBudget

K=C.WinDLL('kernel32',use_last_error=True)
K.GetProcessTimes.argtypes=[W.HANDLE,C.POINTER(W.FILETIME),C.POINTER(W.FILETIME),C.POINTER(W.FILETIME),C.POINTER(W.FILETIME)]
K.QueryFullProcessImageNameW.argtypes=[W.HANDLE,W.DWORD,W.LPWSTR,C.POINTER(W.DWORD)]
K.GetExitCodeProcess.argtypes=[W.HANDLE,C.POINTER(W.DWORD)]
K.GetCurrentProcess.restype=W.HANDLE


def identity(handle,pid):
    creation,exit,kernel,user=(W.FILETIME() for _ in range(4));size=W.DWORD(32768);buffer=C.create_unicode_buffer(size.value)
    if not K.GetProcessTimes(handle,C.byref(creation),C.byref(exit),C.byref(kernel),C.byref(user)):raise OSError(C.get_last_error(),'GetProcessTimes')
    if not K.QueryFullProcessImageNameW(handle,0,buffer,C.byref(size)):raise OSError(C.get_last_error(),'QueryFullProcessImageNameW')
    return {'pid':pid,'created':creation.dwLowDateTime+(creation.dwHighDateTime<<32),'image':buffer.value}


def self_identity():return identity(K.GetCurrentProcess(),os.getpid())


class OwnedChild:
    def __init__(self,path,mode,phase='never'):
        self.b=NativeFixtureBudget(ROOT)
        if self.b.check()>=1500:raise ValueError('TEST_ADMISSION_CLOSED')
        self.executable=str(Path(getattr(sys,'_base_executable',sys.executable)).resolve())
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=';'.join(str(p) for p in (Path.cwd(),Path.cwd()/'backend',Path.cwd()/'tests',Path(sys.prefix)/'Lib'/'site-packages')))
        self.p=subprocess.Popen([self.executable,str(Path(__file__).with_name('native_continuation_v2_child.py')),str(path),mode,phase],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
        self.handle=self.p._handle;self.started=time.monotonic();self.id=identity(self.handle,self.p.pid)
        if Path(self.id['image']).resolve()!=Path(self.executable).resolve():raise ValueError('FOREIGN_CHILD_IMAGE')
    def verify(self):
        code=W.DWORD()
        if not K.GetExitCodeProcess(self.handle,C.byref(code)):raise OSError(C.get_last_error(),'GetExitCodeProcess')
        if code.value!=259:
            creation,exit,kernel,user=(W.FILETIME() for _ in range(4))
            if not K.GetProcessTimes(self.handle,C.byref(creation),C.byref(exit),C.byref(kernel),C.byref(user)):raise OSError(C.get_last_error(),'GetProcessTimes')
            if creation.dwLowDateTime+(creation.dwHighDateTime<<32)!=self.id['created']:raise ValueError('EXITED_CHILD_IDENTITY_CHANGED')
            return True # image independently verified while alive;retained handle pins the lifetime
        if identity(self.handle,self.p.pid)!=self.id:raise ValueError('CHILD_INCARNATION_CHANGED')
        return True
    def finish(self,*,input=None):
        self.verify();timeout=min(60-(time.monotonic()-self.started),1800-self.b.check())
        if timeout<=0:raise ValueError('CHILD_TIME_BOUND')
        try:out,err=self.p.communicate(input=input,timeout=timeout)
        except subprocess.TimeoutExpired:
            self.verify();self.p.terminate();out,err=self.p.communicate(timeout=min(5,1800-self.b.check()));raise ValueError('EXACT_OWNED_CHILD_TIMEOUT')
        self.verify()
        if self.p.poll() is None:raise ValueError('OWNED_CHILD_NOT_REAPED')
        try:self.b.write(ROOT/'evidence'/('child-'+str(self.p.pid)+'-'+str(self.id['created'])+'.json'),body({'process':self.id,'returncode':self.p.returncode,'output':out.decode(errors='replace')[:2048],'error':err.decode(errors='replace')[:4096],'reaped':True,'retained_handle_closed':True}).encode())
        finally:self.handle.Close()
        return self.p.returncode,out,err


def owned_junction(link,target,budget):
    """Observe cmd while suspended,then resume only this retained test handle."""
    link,target=Path(link),Path(target)
    if not link.is_relative_to(ROOT) or not target.is_relative_to(ROOT):raise ValueError('JUNCTION_SCOPE')
    exe=Path(os.environ['SystemRoot'])/'System32'/'cmd.exe'
    proc=subprocess.Popen([str(exe),'/d','/c','mklink','/J',str(link),str(target)],creationflags=4,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    handle=proc._handle
    try:
        before=identity(handle,proc.pid)
        if Path(before['image']).resolve()!=exe.resolve():raise ValueError('FOREIGN_JUNCTION_CHILD')
        native=C.WinDLL('ntdll');native.NtResumeProcess.argtypes=[W.HANDLE];native.NtResumeProcess.restype=C.c_long
        if native.NtResumeProcess(handle)!=0:raise OSError('Could not resume exact test helper')
        try:out,err=proc.communicate(timeout=min(20,1800-budget.check()))
        except subprocess.TimeoutExpired:
            # Retained handle pins exact identity;never discover a process by name.
            proc.terminate();out,err=proc.communicate(timeout=5);raise ValueError('JUNCTION_CHILD_TIMEOUT')
        creation,exit,kernel,user=(W.FILETIME() for _ in range(4))
        if not K.GetProcessTimes(handle,C.byref(creation),C.byref(exit),C.byref(kernel),C.byref(user)) or creation.dwLowDateTime+(creation.dwHighDateTime<<32)!=before['created']:raise ValueError('JUNCTION_CHILD_CHANGED')
        return proc.returncode,out,err,{'process':before,'returncode':proc.returncode,'reaped':proc.poll() is not None,'retained_handle_closed':True}
    finally:
        if proc.poll() is None:
            proc.terminate();proc.wait(timeout=5)
        handle.Close()
