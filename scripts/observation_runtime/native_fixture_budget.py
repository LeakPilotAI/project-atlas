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



def reserve_budget(usage,*,entries,size,unit,max_entries=FILES,max_bytes=BYTES):
    """Pure prospective reservation;invalid/unknown counters can never reset usage."""
    if (type(usage) is not dict or set(usage)!={'entries','charged_bytes'}
            or any(type(v) is not int or v<0 for v in usage.values())
            or type(entries) is not int or entries not in (0,1)
            or type(size) is not int or not 0<=size<=1024*1024
            or type(unit) is not int or not 512<=unit<=2**20 or unit&(unit-1)):
        raise BudgetRefused('RESERVATION_LEDGER_SCHEMA')
    if (type(max_entries) is not int or not 1<=max_entries<=FILES
            or type(max_bytes) is not int or not 4096<=max_bytes<=BYTES):raise BudgetRefused('BOUNDED_LIMITS_REQUIRED')
    reserve=(max(1,math.ceil(size/unit))+2)*unit
    if (usage['entries']>=max_entries or usage['entries']+entries>max_entries
            or usage['charged_bytes']+reserve>max_bytes):raise BudgetRefused('PROSPECTIVE_RESOURCE_LIMIT')
    return {'entries':usage['entries']+entries,'charged_bytes':usage['charged_bytes']+reserve}


def session_limits(authorization,root):
    from scripts.observation_runtime.personal_native_scope import (
        AUTHORIZATION,
        require_scope,
    )
    if authorization==AUTHORIZATION:return require_scope(authorization,str(root))
    if authorization not in ('P-ATLAS-NATIVE-CONTINUATION-DISPOSABLE-V1','P-ATLAS-NATIVE-CONTINUATION-DISPOSABLE-V2'):
        raise BudgetRefused('UNKNOWN_FIXTURE_AUTHORIZATION')
    if authorization.endswith('-V2') and Path(root)!=BASE/'continuation-fixture-77a93d8995474d649d7bda5095d84ab5':
        raise BudgetRefused('EXACT_V2_APPROVED_ROOT_REQUIRED')
    return SECONDS,FILES,BYTES


class NativeFixtureBudget:
    def __init__(self,root):
        self.root=Path(root).absolute()
        if (self.root.parent!=BASE or re.fullmatch(r'continuation-fixture-[0-9a-f]{32}',self.root.name) is None
                or any(p.is_symlink() or p.is_junction() for p in (self.root,*self.root.parents))):
            raise BudgetRefused('EXACT_APPROVED_FIXTURE_ROOT_REQUIRED')
        self.meta=self.root/'session-budget.json';self.lock=self.root/'session-budget.lock'
        self.confined_path(self.meta);self.confined_path(self.lock)
        self.anchor=json.loads(self.meta.read_text(encoding='utf8'))
        if self.anchor['schema']!='APPROVED_NATIVE_FIXTURE_BUDGET_V1':raise BudgetRefused('BUDGET_SCHEMA')
        self.check()

    def confined_path(self,path,*,missing_leaf=False):
        path=Path(path).absolute()
        if path!=self.root and not path.is_relative_to(self.root):raise BudgetRefused('OUTSIDE_FIXTURE_ROOT')
        for part in reversed((path,*path.parents)):
            if part!=self.root and not part.is_relative_to(self.root):continue
            try:st=part.lstat()
            except FileNotFoundError:
                if part==path and missing_leaf:return path
                raise BudgetRefused('MISSING_CONTROL_NAMESPACE') from None
            if part.is_symlink() or part.is_junction() or part.is_file() and st.st_nlink!=1:
                raise BudgetRefused('CONTROL_NAMESPACE_LINK_REFUSED')
        return path

    def limits(self):
        limits=session_limits(self.anchor['authorization'],self.root)
        if (any(type(self.anchor[k]) is not int for k in ('seconds','entries','charged_bytes'))
                or tuple(self.anchor[k] for k in ('seconds','entries','charged_bytes'))!=limits):raise BudgetRefused('BUDGET_LIMITS_CHANGED')
        return limits

    def check(self):
        seconds,_,_=self.limits()
        for binding in reversed(self.anchor.get('namespace',[])):
            path=Path(binding['path']);st=path.lstat()
            if path.is_symlink() or path.is_junction() or [st.st_dev,st.st_ino]!=binding['identity']:
                raise BudgetRefused('BUDGET_NAMESPACE_IDENTITY_CHANGED')
        elapsed=(time.monotonic_ns()-self.anchor['started_monotonic_ns'])/1e9
        if elapsed<0 or elapsed>=seconds:raise BudgetRefused('30_MINUTE_EXECUTION_LIMIT' if seconds==1800 else '10_MINUTE_EXECUTION_LIMIT')
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

    def usage(self,*,allow_links=False):
        _,files,byte_limit=self.limits()
        count=int(self.anchor['authorization'] in ('P-ATLAS-PERSONAL-NATIVE-COMPATIBILITY-V1','P-ATLAS-PERSONAL-NATIVE-COMPATIBILITY-V2','P-ATLAS-PERSONAL-NATIVE-COMPATIBILITY-V3','P-ATLAS-PERSONAL-NATIVE-COMPATIBILITY-V4','P-ATLAS-PERSONAL-NATIVE-COMPATIBILITY-V5'));logical=0;charged=0;unit=self.anchor['allocation_unit']
        if count:charged=2*unit
        pending=[self.root]
        while pending:
            for p in pending.pop().iterdir():
                link=p.is_symlink() or p.is_junction()
                if link and not allow_links:raise BudgetRefused('UNEXPECTED_REPARSE_POINT')
                count+=1
                if count>files:raise BudgetRefused('FILE_ENTRY_LIMIT')
                size=p.lstat().st_size if link else p.stat().st_size if p.is_file() else 0
                logical+=size;charged+=(max(1,math.ceil(size/unit))+1)*unit
                if charged>byte_limit:raise BudgetRefused('STORAGE_LIMIT')
                if not link and p.is_dir():pending.append(p)
        return {'entries':count,'logical_bytes':logical,'charged_bytes':charged,'elapsed_seconds':round(self.check(),3)}

    @contextmanager
    def mutation(self,path,*,entries=1,size=0):
        path=Path(path).absolute()
        if not path.is_relative_to(self.root) or path==self.root:raise BudgetRefused('OUTSIDE_FIXTURE_ROOT')
        if any(p.is_symlink() or p.is_junction() for p in reversed((path,*path.parents)) if p==self.root or p.is_relative_to(self.root)):
            raise BudgetRefused('MUTATION_NAMESPACE_SUBSTITUTION')
        if path.exists() and path.is_file() and path.stat().st_nlink!=1:
            raise BudgetRefused('MUTATION_HARDLINK')
        with self.lease():
            # Durable monotone reservations avoid repeated full-tree traversal and
            # conservatively charge failed writes and replacements;never refund.
            ledger=self.root/'session-reservations.json'
            if not ledger.exists() or ledger.is_symlink() or ledger.is_junction() or ledger.stat().st_nlink!=1:
                raise BudgetRefused('RESERVATION_LEDGER_MISSING_OR_SUBSTITUTED')
            try:usage=json.loads(ledger.read_text(encoding='utf8'))
            except (ValueError,OSError) as exc:raise BudgetRefused('RESERVATION_LEDGER_CORRUPT') from exc
            _,files,byte_limit=self.limits()
            usage=reserve_budget(usage,entries=entries,size=size,unit=self.anchor['allocation_unit'],max_entries=files,max_bytes=byte_limit)
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
        path=self.confined_path(path,missing_leaf=True)
        if len(data)>1024*1024:raise BudgetRefused('BOUNDED_CONTROL_EVIDENCE')
        try:path.lstat();exists=True
        except FileNotFoundError:exists=False
        with self.mutation(path,entries=0 if exists else 1,size=len(data)), path.open('wb' if replace else 'xb') as stream:
                stream.write(data);stream.flush();os.fsync(stream.fileno())

    def native_write(self,output,name,data):
        with self.mutation(Path(output.root)/name,size=len(data)):
            return output.write_bound(name,data)


def create_session(root,*,started_monotonic_ns,authorization="P-ATLAS-NATIVE-CONTINUATION-DISPOSABLE-V1"):
    root=Path(root).absolute()
    seconds,files,byte_limit=session_limits(authorization,root)
    if root.exists() or root.parent!=BASE or re.fullmatch(r'continuation-fixture-[0-9a-f]{32}',root.name) is None:
        raise BudgetRefused('ONE_NEW_ROOT_ONLY')
    elapsed=(time.monotonic_ns()-started_monotonic_ns)/1e9
    if not 0<=elapsed<seconds:raise BudgetRefused('SESSION_ALREADY_EXPIRED')
    sectors=ctypes.c_ulong();bytes_sector=ctypes.c_ulong();free=ctypes.c_ulong();total=ctypes.c_ulong()
    if not ctypes.windll.kernel32.GetDiskFreeSpaceW(str(root.anchor),ctypes.byref(sectors),ctypes.byref(bytes_sector),ctypes.byref(free),ctypes.byref(total)):
        raise OSError('Allocation geometry unavailable')
    unit=sectors.value*bytes_sector.value
    if not 512<=unit<=2**20:raise BudgetRefused('UNSUPPORTED_VOLUME_ALLOCATION_UNIT')
    if any(p.is_symlink() or p.is_junction() for p in root.parents):raise BudgetRefused('ANCESTOR_REPARSE')
    if not 0<=(time.monotonic_ns()-started_monotonic_ns)/1e9<seconds:raise BudgetRefused('SESSION_EXPIRED_BEFORE_FIRST_CREATE')
    root.mkdir(exist_ok=False)
    anchor={'schema':'APPROVED_NATIVE_FIXTURE_BUDGET_V1','started_monotonic_ns':started_monotonic_ns,
            'allocation_unit':unit,'authorization':authorization,
            'seconds':seconds,'entries':files,'charged_bytes':byte_limit,
            'namespace':[{'path':str(p),'identity':[p.lstat().st_dev,p.lstat().st_ino]} for p in (root,*root.parents)]}
    with (root/'session-budget.json').open('x',encoding='utf8') as stream:json.dump(anchor,stream)
    with (root/'session-budget.lock').open('xb') as stream:stream.write(b'0')
    with (root/'session-reservations.json').open('x',encoding='utf8') as stream:
        json.dump({'entries':4 if authorization in ('P-ATLAS-PERSONAL-NATIVE-COMPATIBILITY-V1','P-ATLAS-PERSONAL-NATIVE-COMPATIBILITY-V2','P-ATLAS-PERSONAL-NATIVE-COMPATIBILITY-V3','P-ATLAS-PERSONAL-NATIVE-COMPATIBILITY-V4','P-ATLAS-PERSONAL-NATIVE-COMPATIBILITY-V5') else 3,'charged_bytes':unit*12},stream);stream.flush();os.fsync(stream.fileno())
    return NativeFixtureBudget(root)
