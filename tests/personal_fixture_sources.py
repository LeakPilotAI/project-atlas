"""Test-only installed-source selection, never operational enrollment or launch.

Keeps synthetic account confinement in the workspace while native codec and
application imports come from an explicitly pinned disposable installation.
"""
import ctypes as C
import hashlib
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath


def validate_scope(workspace,raw,pin,executable,prefix):
    if len(raw)>1024*1024 or not re.fullmatch('[0-9a-f]{64}',pin) or hashlib.sha256(raw).hexdigest()!=pin:
        raise ValueError('SYNTHETIC_INSTALL_SCOPE_PIN')
    scope=json.loads(raw)
    if (type(scope) is not dict or set(scope)!={'schema','root','source_commit','files'}
            or scope['schema']!='PINNED_SYNTHETIC_INSTALL_V1'
            or type(scope['root']) is not str or type(scope['source_commit']) is not str
            or not re.fullmatch('[0-9a-f]{40}',scope['source_commit'])
            or type(scope['files']) is not list or not 0<len(scope['files'])<=2048):
        raise ValueError('SYNTHETIC_INSTALL_SCOPE_REQUIRED')
    root=Path(scope['root'])
    if (not root.is_absolute() or root.name!='candidate' or root.parent.parent!=workspace/'logs/diagnostics'
            or not root.parent.name.startswith('qd-native-install-')
            or Path(executable)!=root/'python/python.exe' or Path(prefix)!=root/'python'):
        raise ValueError('SYNTHETIC_INSTALLED_IMAGE_REQUIRED')
    rows={}
    for row in scope['files']:
        if (type(row) is not dict or set(row)!={'path','bytes','sha256','id'}
                or type(row['path']) is not str or type(row['sha256']) is not str):
            raise ValueError('SYNTHETIC_INSTALLED_SOURCE_INVENTORY')
        name=row['path'];path=PurePosixPath(name)
        if (set(row)!={'path','bytes','sha256','id'} or type(name) is not str or path.is_absolute()
                or path.as_posix()!=name or '\\' in name or ':' in name or '..' in path.parts
                or name in rows or type(row['bytes']) is not int or row['bytes']<0
                or not re.fullmatch('[0-9a-f]{64}',row['sha256']) or type(row['id']) is not list
                or len(row['id'])!=3 or any(type(n) is not int or n<0 for n in row['id'])):
            raise ValueError('SYNTHETIC_INSTALLED_SOURCE_INVENTORY')
        rows[name]=row
    return root,rows


def fixture_source_root(workspace):
    """Default workspace tests unchanged; installed mode is explicitly synthetic."""
    configured=os.environ.get('ATLAS_SYNTHETIC_INSTALL_SCOPE')
    pin=os.environ.get('ATLAS_SYNTHETIC_INSTALL_SCOPE_SHA256')
    if configured is None and pin is None:return workspace
    if configured is None or pin is None:raise ValueError('COMPLETE_SYNTHETIC_INSTALL_SCOPE_REQUIRED')
    scope_path=Path(configured)
    if (scope_path.name!='installed-fixture-scope.json' or scope_path.parent.parent!=workspace/'logs/diagnostics'
            or not scope_path.parent.name.startswith('qd-native-install-')):
        raise ValueError('CONFINED_SYNTHETIC_INSTALL_SCOPE_REQUIRED')
    for p in (scope_path,*scope_path.parents):
        if p.is_symlink() or p.is_junction():raise ValueError('FIXTURE_SCOPE_LINK')
    with scope_path.open('rb') as stream:raw=stream.read(1024*1024+1)
    root,rows=validate_scope(workspace,raw,pin,sys.executable,sys.base_prefix)
    for p in (root,*root.parents):
        if p.is_symlink() or p.is_junction():raise ValueError('FIXTURE_SOURCE_LINK')
    from scripts.volume_inspector import windows_output as w
    names=set()
    for name,module in tuple(sys.modules.items()):
        if name=='app' or name.startswith(('app.','scripts.observation_runtime.','scripts.volume_inspector.')):
            filename=getattr(module,'__file__',None)
            if filename is None:
                for location in getattr(module,'__path__',()):
                    if not Path(location).is_relative_to(root):raise ValueError('MIXED_SYNTHETIC_MODULE_NAMESPACE')
                continue
            path=Path(filename)
            if not path.is_relative_to(root) or getattr(getattr(module,'__spec__',None),'origin',None)!=filename:
                raise ValueError('MIXED_SYNTHETIC_MODULE_ORIGIN')
            names.add(path.relative_to(root).as_posix())
    # Test fixtures dynamically load these exact codecs; verify before that access.
    names.update(('scripts/volume_inspector/operational_autonomous_store.py','scripts/volume_inspector/financial_reporting.py'))
    for name in sorted(names):
        if name not in rows:raise ValueError('MODULE_OUTSIDE_SYNTHETIC_INSTALL_INVENTORY')
        row=rows[name];path=root/name
        with w.WindowsOutput(str(path.parent)) as directory:
            handle=w.relative_open(directory.root_handle,path.name,directory.sid,False,access=w.READ|w.READ_CONTROL)
            try:
                w.validate_acl(handle,directory.sid);info=w.info(handle)
                if [info.volume,info.index_hi,info.index_lo]!=row['id'] or info.links!=1:
                    raise ValueError('SYNTHETIC_INSTALLED_MODULE_SUBSTITUTION')
                checksum=hashlib.sha256();length=0
                while True:
                    buf=C.create_string_buffer(65536);count=w.W.DWORD()
                    w.check(w.read_file(handle,buf,65536,C.byref(count),None))
                    if not count.value:break
                    length+=count.value
                    if length>row['bytes']:raise ValueError('SYNTHETIC_MODULE_GROWTH')
                    checksum.update(buf.raw[:count.value])
                if length!=row['bytes'] or checksum.hexdigest()!=row['sha256']:
                    raise ValueError('SYNTHETIC_INSTALLED_MODULE_CONTENT')
            finally:w.close_handle(handle)
    return root
