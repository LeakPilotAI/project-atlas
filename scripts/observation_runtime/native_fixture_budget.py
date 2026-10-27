"""One approved native fixture session. No operational paths or trust authority."""
import ctypes
import json
import math
import os
import re
import time
from contextlib import contextmanager
from pathlib import Path

BASE=Path(__file__).resolve().parents[2]/'logs/diagnostics'
FILES=8192
BYTES=256*1024*1024
SECONDS=1800


class BudgetRefused(ValueError):pass


class NativeFixtureBudget:
    def __init__(self,root):
        self.root=Path(root).absolute()
        if (self.root.parent!=BASE or re.fullmatch(r'continuation-fixture-[0-9a-f]{32}',self.root.name) is None
                or any(p.is_symlink() or p.is_junction() for p in (self.root,*self.root.parents))):
            raise BudgetRefused('EXACT_APPROVED_FIXTURE_ROOT_REQUIRED')
        self.meta=self.root/'session-budget.json';self.lock=self.root/'session-budget.lock'
        self.anchor=json.loads(self.meta.read_text(encoding='utf8'))
        if self.anchor['schema']!='APPROVED_NATIVE_FIXTURE_BUDGET_V1':raise BudgetRefused('BUDGET_SCHEMA')
        self.check()

    def check(self):
        elapsed=(time.monotonic_ns()-self.anchor['started_monotonic_ns'])/1e9
        if elapsed<0 or elapsed>=SECONDS:raise BudgetRefused('30_MINUTE_EXECUTION_LIMIT')
        if not self.root.is_dir() or self.root.is_symlink() or self.root.is_junction():raise BudgetRefused('ROOT_CHANGED')
        return elapsed

    @contextmanager
    def lease(self):
        import msvcrt
        self.check()
        with self.lock.open('r+b') as stream:
            deadline=time.monotonic()+30
            while True:
                self.check()
                try:
                    msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1);break
                except OSError:
                    if time.monotonic()>=deadline:raise BudgetRefused('BOUNDED_LOCK_TIMEOUT')
                    time.sleep(0.02)
            try:self.check();yield
            finally:stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)

    def usage(self):
        count=0;logical=0;charged=0;unit=self.anchor['allocation_unit']
        pending=[self.root]
        while pending:
            for p in pending.pop().iterdir():
                if p.is_symlink() or p.is_junction():raise BudgetRefused('UNEXPECTED_REPARSE_POINT')
                count+=1
                if count>FILES:raise BudgetRefused('FILE_ENTRY_LIMIT')
                size=p.stat().st_size if p.is_file() else 0
                logical+=size;charged+=(max(1,math.ceil(size/unit))+1)*unit
                if charged>BYTES:raise BudgetRefused('STORAGE_LIMIT')
                if p.is_dir():pending.append(p)
        return {'entries':count,'logical_bytes':logical,'charged_bytes':charged,'elapsed_seconds':round(self.check(),3)}

    @contextmanager
    def mutation(self,path,*,entries=1,size=0):
        path=Path(path).absolute()
        if not path.is_relative_to(self.root) or path==self.root:raise BudgetRefused('OUTSIDE_FIXTURE_ROOT')
        if any(p.is_symlink() or p.is_junction() for p in (path,*path.parents) if p==self.root or p.is_relative_to(self.root)):
            raise BudgetRefused('MUTATION_NAMESPACE_SUBSTITUTION')
        if path.exists() and path.is_file() and path.stat().st_nlink!=1:
            raise BudgetRefused('MUTATION_HARDLINK')
        with self.lease():
            # Durable monotone reservations avoid repeated full-tree traversal and
            # conservatively charge failed writes and replacements;never refund.
            ledger=self.root/'session-reservations.json'
            if ledger.exists():
                usage=json.loads(ledger.read_text(encoding='utf8'))
            else:
                usage=self.usage()
                usage['entries']+=1
                usage['charged_bytes']+=self.anchor['allocation_unit']*4
            unit=self.anchor['allocation_unit']
            reserve=(max(1,math.ceil(size/unit))+2)*unit
            if usage['entries']+entries>FILES or usage['charged_bytes']+reserve>BYTES:
                raise BudgetRefused('PROSPECTIVE_RESOURCE_LIMIT')
            usage['entries']+=entries;usage['charged_bytes']+=reserve
            with ledger.open('w',encoding='utf8') as stream:
                json.dump(usage,stream);stream.flush();os.fsync(stream.fileno())
            yield
            self.check()

    def directory(self,path,*,native_factory=None):
        with self.mutation(path):
            if native_factory is None:Path(path).mkdir(exist_ok=False)
            else:
                with native_factory(str(path)):pass

    def write(self,path,data,*,replace=False):
        path=Path(path)
        if len(data)>1024*1024:raise BudgetRefused('BOUNDED_CONTROL_EVIDENCE')
        with self.mutation(path,entries=0 if path.exists() else 1,size=len(data)), path.open('wb' if replace else 'xb') as stream:
                stream.write(data);stream.flush();os.fsync(stream.fileno())

    def native_write(self,output,name,data):
        with self.mutation(Path(output.root)/name,size=len(data)):
            return output.write_bound(name,data)


def create_session(root,*,started_monotonic_ns):
    root=Path(root).absolute()
    if root.exists() or root.parent!=BASE or re.fullmatch(r'continuation-fixture-[0-9a-f]{32}',root.name) is None:
        raise BudgetRefused('ONE_NEW_ROOT_ONLY')
    elapsed=(time.monotonic_ns()-started_monotonic_ns)/1e9
    if not 0<=elapsed<SECONDS:raise BudgetRefused('SESSION_ALREADY_EXPIRED')
    sectors=ctypes.c_ulong();bytes_sector=ctypes.c_ulong();free=ctypes.c_ulong();total=ctypes.c_ulong()
    if not ctypes.windll.kernel32.GetDiskFreeSpaceW(str(root.anchor),ctypes.byref(sectors),ctypes.byref(bytes_sector),ctypes.byref(free),ctypes.byref(total)):
        raise OSError('Allocation geometry unavailable')
    unit=sectors.value*bytes_sector.value
    if not 512<=unit<=2**20:raise BudgetRefused('UNSUPPORTED_VOLUME_ALLOCATION_UNIT')
    root.mkdir(exist_ok=False)
    anchor={'schema':'APPROVED_NATIVE_FIXTURE_BUDGET_V1','started_monotonic_ns':started_monotonic_ns,
            'allocation_unit':unit,'authorization':'P-ATLAS-NATIVE-CONTINUATION-DISPOSABLE-V1',
            'seconds':SECONDS,'entries':FILES,'charged_bytes':BYTES}
    with (root/'session-budget.json').open('x',encoding='utf8') as stream:json.dump(anchor,stream)
    with (root/'session-budget.lock').open('xb') as stream:stream.write(b'0')
    return NativeFixtureBudget(root)

