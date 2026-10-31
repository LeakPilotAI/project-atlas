"""Accounting for declared negative fixtures; never financial/native admission.

Probe declarations explain only test-owned aliases. Candidate namespaces retain
their unconditional no-hardlink policy. Local declarations are not trust roots.
"""
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

PROBE_OWNER='tests/test_candidate_source_identity.py::test_native_hard_link_source_is_not_read'


def inside(path,root):
    path,root=Path(os.path.abspath(path)),Path(os.path.abspath(root))
    if not path.is_relative_to(root):raise ValueError('TEST_SCOPE_ESCAPE')
    for node in (path,*path.parents):
        if os.path.lexists(node):
            value=node.lstat()
            if getattr(value,'st_file_attributes',0)&0x400 or stat.S_ISLNK(value.st_mode):
                raise ValueError('TEST_SCOPE_REPARSE')
    return path


def _unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('DUPLICATE_PROBE_FIELD')
        result[key]=value
    return result


def declare_probe(root,fixture,*,owner=PROBE_OWNER):
    root=inside(root,root);fixture=inside(fixture,root)
    relative=fixture.relative_to(root)
    if owner!=PROBE_OWNER or len(relative.parts)!=2 or relative.parts[0]!='pytest':
        raise ValueError('EXACT_NEGATIVE_PROBE_FIXTURE_REQUIRED')
    if not fixture.is_dir():raise ValueError('EXISTING_OWNED_PROBE_PARENT_REQUIRED')
    info=fixture.lstat()
    paths=[(relative/'source/backend/app/example.py').as_posix(),(relative/'outside-source.py').as_posix()]
    registry=inside(root/'probe-registry',root)
    if not registry.is_dir():raise ValueError('TEST_CONTROLLER_REGISTRY_REQUIRED')
    # Declaration precedes the test, not a post-hoc whitelist after refusal.
    if any(os.path.lexists(root/name) for name in paths):raise ValueError('PROBE_MUST_BE_DECLARED_BEFORE_CREATION')
    row={'schema':'QD_NEGATIVE_HARDLINK_PROBE_V1','owner':owner,'fixture':relative.as_posix(),
        'parent_identity':[info.st_dev,info.st_ino],'paths':paths}
    name=hashlib.sha256(relative.as_posix().encode()).hexdigest()+'.json'
    with (registry/name).open('xb') as stream:
        stream.write(json.dumps(row,sort_keys=True).encode());stream.flush();os.fsync(stream.fileno())
    return row


def probe_paths(root):
    root=inside(root,root);registry=root/'probe-registry'
    if not registry.exists():return {}
    inside(registry,root);rows=list(registry.iterdir())
    if len(rows)>64:raise ValueError('PROBE_REGISTRY_CAPACITY')
    result={}
    for path in rows:
        inside(path,root);info=path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>4096:
            raise ValueError('PROBE_RECORD_IDENTITY_OR_CAPACITY')
        row=json.loads(path.read_bytes(),object_pairs_hook=_unique)
        if (type(row) is not dict or set(row)!={'schema','owner','fixture','parent_identity','paths'}
                or row['schema']!='QD_NEGATIVE_HARDLINK_PROBE_V1' or row['owner']!=PROBE_OWNER
                or type(row['fixture']) is not str):raise ValueError('EXACT_PROBE_DECLARATION_REQUIRED')
        relative=Path(row['fixture']);fixture=inside(root/relative,root)
        if len(relative.parts)!=2 or relative.parts[0]!='pytest' or relative.as_posix()!=row['fixture']:
            raise ValueError('EXACT_NEGATIVE_PROBE_FIXTURE_REQUIRED')
        expected=[(relative/'source/backend/app/example.py').as_posix(),(relative/'outside-source.py').as_posix()]
        if row['paths']!=expected:raise ValueError('EXACT_PROBE_ALIAS_PAIR_REQUIRED')
        parent=fixture.lstat()
        if row['parent_identity']!=[parent.st_dev,parent.st_ino]:raise ValueError('PROBE_PARENT_SUBSTITUTION')
        if path.name!=hashlib.sha256(relative.as_posix().encode()).hexdigest()+'.json':
            raise ValueError('PROBE_RECORD_NAME_MISMATCH')
        group=tuple(expected)
        for name in expected:
            if name in result:raise ValueError('DUPLICATE_PROBE_ALIAS')
            result[name]=group
    return result


def account(root,*,allocation_unit=4096):
    root=inside(root,root);declared=probe_paths(root)
    if type(allocation_unit) is not int or not 512<=allocation_unit<=65536 or allocation_unit&(allocation_unit-1):
        raise ValueError('ALLOCATION_UNIT_REQUIRED')
    entries,logical,files,directories=1,0,0,1
    groups={};observed={}
    for parent,dirs,names in os.walk(root,followlinks=False):
        for name in dirs+names:
            path=Path(parent)/name;info=path.lstat();entries+=1
            if getattr(info,'st_file_attributes',0)&0x400 or stat.S_ISLNK(info.st_mode):raise ValueError('TEST_SCOPE_REPARSE')
            if stat.S_ISDIR(info.st_mode):directories+=1;continue
            if not stat.S_ISREG(info.st_mode):raise ValueError('TEST_SCOPE_SPECIAL_FILE')
            files+=1;logical+=info.st_size
            relative=path.relative_to(root).as_posix();observed[relative]=(info.st_dev,info.st_ino,info.st_nlink)
            if info.st_nlink!=1:
                if relative not in declared:raise ValueError('UNDECLARED_TEST_HARDLINK')
                groups.setdefault((info.st_dev,info.st_ino),[]).append((relative,info.st_nlink))
    for identity,aliases in groups.items():
        expected=set(declared[aliases[0][0]])
        if ({name for name,_ in aliases}!=expected or any(count!=len(expected) for _,count in aliases)
                or any(observed.get(name)!=(identity[0],identity[1],len(expected)) for name in expected)):
            raise ValueError('EXTERNAL_OR_INCOMPLETE_TEST_HARDLINK_GROUP')
    return {'entries':entries,'files':files,'directories':directories,'logical_bytes':logical,
        'allocation_upper_bound_bytes':logical+entries*allocation_unit,'declared_materialized_groups':len(groups)}


def confined_environment(root,base=None):
    root=inside(root,root);env=dict(os.environ if base is None else base)
    env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
        TEMP=str(root),TMP=str(root),PYTHONPYCACHEPREFIX=str(root/'unused-pycache'),
        RUFF_NO_CACHE='1',RUFF_CACHE_DIR=str(root/'unused-ruff-cache'),XDG_CACHE_HOME=str(root/'cache'))
    env.pop('PYTHONHOME',None)
    env.pop('PYTEST_ADDOPTS',None)
    return env


def install_write_audit(root):
    """Python-level test instrumentation, not a native/process security sandbox."""
    root=os.path.realpath(root);state={'allowed_write_events':0,'denied':[]}
    abspath,realpath,lstat,lexists=os.path.abspath,os.path.realpath,os.lstat,os.path.lexists
    def check(path):
        if isinstance(path,int):
            if path in (0,1,2):return
            if os.name!='nt':raise PermissionError('UNRESOLVED_WRITE_DESCRIPTOR')
            import ctypes
            import msvcrt
            from ctypes import wintypes
            kernel=ctypes.WinDLL('kernel32',use_last_error=True);handle=msvcrt.get_osfhandle(path)
            kernel.GetFileType.argtypes=[wintypes.HANDLE];kernel.GetFileType.restype=wintypes.DWORD
            if kernel.GetFileType(handle)==3:return  # process pipe, not a file
            final=kernel.GetFinalPathNameByHandleW
            final.argtypes=[wintypes.HANDLE,wintypes.LPWSTR,wintypes.DWORD,wintypes.DWORD];final.restype=wintypes.DWORD
            buf=ctypes.create_unicode_buffer(32768);n=final(handle,buf,len(buf),0)
            if not 0<n<len(buf):raise PermissionError('UNRESOLVED_WRITE_DESCRIPTOR')
            path=buf.value.removeprefix('\\\\?\\')
        path=os.fsdecode(path)
        if path.upper() in ('NUL',os.devnull.upper(),'\\\\.\\NUL'):return  # Windows null device, not a filesystem output
        lexical=abspath(path);resolved=realpath(lexical)
        try:valid=os.path.commonpath([root,resolved])==root and os.path.commonpath([root,lexical])==root
        except ValueError:valid=False
        if not valid:raise PermissionError('WRITE_OUTSIDE_DISPOSABLE_SCOPE:'+lexical)
        node=lexical
        while True:
            if lexists(node):
                info=lstat(node)
                if getattr(info,'st_file_attributes',0)&0x400 or stat.S_ISLNK(info.st_mode):
                    raise PermissionError('WRITE_THROUGH_REPARSE_REFUSED')
            parent=os.path.dirname(node)
            if parent==node:break
            node=parent
    def audit(event,args):
        paths=[]
        if event=='open':
            path,mode,flags=args
            if (mode and any(c in mode for c in 'wax+')) or flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):paths=[path]
        elif event in ('os.mkdir','os.remove','os.rmdir','os.chmod','os.truncate','os.utime'):paths=[args[0]]
        elif event in ('os.rename','os.link'):paths=list(args[:2])
        elif event=='os.symlink':raise PermissionError('SYMLINK_CREATION_NOT_NEEDED_FOR_OFFLINE_CLOSURE')
        try:
            for path in paths:check(path)
        except (ValueError,OSError) as error:
            state['denied'].append({'event':event,'reason':str(error)[:1024]})
            raise
        if paths:state['allowed_write_events']+=1
    sys.addaudithook(audit)
    return state


def preserve_terminal_accounting(result,root,started,*,now,limit):
    """Accounting refusal never erases the original failure or implies success."""
    result=dict(result);result['seconds']=round(now-started,3)
    try:
        counts=account(root)
        if counts['entries']>=40000 or counts['allocation_upper_bound_bytes']>=1024**3 or now-started>=limit:
            raise ValueError('TEST_SCOPE_RESOURCE_LIMIT')
        result['resource_accounting']=counts
    except (ValueError,OSError,KeyError,TypeError) as error:
        result['accounting_error']=type(error).__name__+':'+str(error)
        result['status']='REFUSED_PRESERVE_PARTIAL'
    return result
