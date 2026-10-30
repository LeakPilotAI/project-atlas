"""Explicit disposable Windows installation, never operational release promotion.

Reuses the native creation-handle/owner-SYSTEM primitives. No default CLI,
financial enrollment, provider, process launcher, active selector or repair.
"""
from __future__ import annotations

import ctypes as C
import hashlib
import io
import json
import os
import stat
import time
import zipfile
from contextlib import ExitStack, contextmanager
from pathlib import Path


def _verify_namespace(root,files,directories,bound):
    """Refuse incomplete/unlisted namespace before a candidate can be executed."""
    actual_files=set();actual_dirs={'.'}
    for parent,dirs,names in os.walk(root,followlinks=False):
        bound()
        for name in dirs+names:
            path=Path(parent)/name;info=path.lstat()
            if getattr(info,'st_file_attributes',0)&0x400:
                raise ValueError('CANDIDATE_REPARSE_REFUSED')
            relative=path.relative_to(root).as_posix()
            if stat.S_ISDIR(info.st_mode):
                if relative not in directories:raise ValueError('UNLISTED_CANDIDATE_DIRECTORY')
                actual_dirs.add(relative)
            elif stat.S_ISREG(info.st_mode) and info.st_nlink==1:
                if relative not in files:raise ValueError('UNLISTED_CANDIDATE_FILE')
                actual_files.add(relative)
            else:raise ValueError('CANDIDATE_SPECIAL_OR_LINKED_FILE')
    if actual_files!=set(files) or actual_dirs!=set(directories):
        raise ValueError('INCOMPLETE_CANDIDATE_NAMESPACE')


def install_synthetic_candidate(*, destination, archive, archive_sha256, source_commit,
                                dependency_receipt, dependency_digest, observer=None,
                                interrupt_after=None):
    """Install only a NEW confined test candidate. Partial evidence is retained.

    Receipt identifies synthetic installation evidence, not operational trust.
    Bounds include all copying and final native readback; no child is launched.
    """

    if (observer is not None and not callable(observer) or interrupt_after is not None
            and (type(interrupt_after) is not int or interrupt_after<1)):
        raise ValueError('EXPLICIT_TEST_ARGUMENTS_REQUIRED')
    repo=Path(__file__).resolve().parents[1]
    destination=Path(destination).absolute()
    parent=destination.parent
    if (parent.parent!=repo/'logs/diagnostics' or not parent.name.startswith('qd-native-install-')
            or destination.name not in ('candidate','interrupted') or os.path.lexists(destination)
            or not parent.is_dir() or any(p.is_symlink() or p.is_junction() for p in (parent,*parent.parents))):
        raise ValueError('EXACT_NEW_DISPOSABLE_INSTALLATION_REQUIRED')
    from scripts.native_install_plan import prepare_install_inputs
    prepared=prepare_install_inputs(archive=archive,archive_sha256=archive_sha256,source_commit=source_commit,
        dependency_receipt=dependency_receipt,dependency_digest=dependency_digest)
    def synthetic_observer(snapshot):
        snapshot['schema']='ATLAS_DISPOSABLE_NATIVE_INSTALLATION_V1'
        if snapshot.get('status')=='NATIVE_COPY_ACL_IDENTITY_HASH_VERIFIED_UNSELECTED':
            snapshot['status']='NATIVE_COPY_ACL_IDENTITY_HASH_VERIFIED_SYNTHETIC_ONLY'
        if observer is not None:observer(snapshot)
    result=_copy_prepared_code(destination=destination,archive_sha256=archive_sha256,source_commit=source_commit,
        prepared=prepared,observer=synthetic_observer if observer is not None else None,interrupt_after=interrupt_after)
    result['schema']='ATLAS_DISPOSABLE_NATIVE_INSTALLATION_V1'
    result['status']='NATIVE_COPY_ACL_IDENTITY_HASH_VERIFIED_SYNTHETIC_ONLY'
    return result


def _copy_prepared_code(*, destination, archive_sha256, source_commit, prepared,
                        observer=None, interrupt_after=None, admission=None):
    # Private physical-copy primitive. Public callers enforce disjoint destination
    # domains. It never selects a release or grants financial/service authority.
    from scripts.volume_inspector import windows_output as w
    source=prepared['source'];dependencies=prepared['dependencies'];runtime=prepared['runtime']
    names=prepared['names'];directories=prepared['directories'];old_dirs=prepared['old_dirs']
    verified=prepared['verified'];bundle=zipfile.ZipFile(io.BytesIO(prepared['raw']))
    started=prepared['started'];charged=0
    result={'schema':'ATLAS_NATIVE_CODE_COPY_V1','source_commit':source_commit,
        'root':str(destination),'archive_sha256':archive_sha256,'files':[],'directories':[],
        'operational_acceptance':False,'active_release_modified':False,'financial_actions':0,
        'limits':{'seconds':600,'entries':40000,'bytes':1024**3},'source_archive':verified}
    targets={};readers={};open_files=[]
    @contextmanager
    def held(output):
        try:yield output
        finally:
            while output.handles:
                handle=output.handles[-1]
                if not w.close_handle(handle):raise OSError('NATIVE_INSTALL_DIRECTORY_CLOSE_UNCONFIRMED')
                output.handles.pop()
    def open_native(*args,**kwargs):
        handle=w.relative_open(*args,**kwargs);open_files.append(handle);return handle
    def close_native(handle):
        if not w.close_handle(handle):raise OSError('NATIVE_INSTALL_FILE_CLOSE_UNCONFIRMED')
        open_files.remove(handle)
    def budget(extra=0):
        if admission is not None and admission() is not True:raise ValueError('INSTALL_ADMISSION_LOST')
        if time.monotonic()-started>600 or charged+extra>1024**3:
            raise ValueError('INSTALL_BOUND_PRESERVE_PARTIAL')
    def notify():
        if observer is not None:observer(json.loads(json.dumps(result,allow_nan=False)))
    def native_id(handle):
        info=w.info(handle);return [info.volume,info.index_hi,info.index_lo]
    try:
        with ExitStack() as stack:
            budget()
            targets['.']=stack.enter_context(held(w.WindowsOutput.create_root(str(destination))))
            result['directories'].append({'path':'.','id':native_id(targets['.'].root_handle)})
            for name in directories:
                budget();targets[name]=stack.enter_context(held(w.WindowsOutput.create_root(str(destination/name))))
                result['directories'].append({'path':name,'id':native_id(targets[name].root_handle)})
            for index,name in enumerate(names):
                budget();row=(dependencies if name in dependencies else runtime)[name]
                if type(row['bytes']) is not int or row['bytes']<0:raise ValueError('INVALID_INPUT_SIZE')
                budget(row['bytes']);relative=Path(name)
                if name in dependencies:
                    directory=relative.parent.as_posix()
                    if directory not in readers:
                        reader=stack.enter_context(held(w.WindowsOutput(str(source/directory))))
                        if native_id(reader.root_handle)!=old_dirs[directory]['id']:
                            raise ValueError('DEPENDENCY_DIRECTORY_SUBSTITUTION')
                        readers[directory]=reader
                    reader=readers[directory];reader._verify()
                    handle=open_native(reader.root_handle,relative.name,reader.sid,False,access=w.READ|w.READ_CONTROL)
                    try:
                        w.validate_acl(handle,reader.sid);info=w.info(handle)
                        if native_id(handle)!=row['id'] or info.links!=1 or (info.size_hi<<32|info.size_lo)!=row['bytes']:
                            raise ValueError('DEPENDENCY_FILE_SUBSTITUTION')
                        chunks=[];length=0
                        while True:
                            budget();buf=C.create_string_buffer(65536);count=w.W.DWORD()
                            w.check(w.read_file(handle,buf,65536,C.byref(count),None))
                            if not count.value:break
                            length+=count.value
                            if length>row['bytes']:raise ValueError('DEPENDENCY_GROWTH')
                            chunks.append(buf.raw[:count.value])
                        data=b''.join(chunks)
                    finally:close_native(handle)
                else:data=bundle.read(name)
                if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256']:
                    raise ValueError('INSTALL_INPUT_CONTENT_CHANGED')
                out=targets[relative.parent.as_posix()];out._verify()
                handle=open_native(out.root_handle,relative.name,out.sid,False,create=True,access=w.READ|w.WRITE|w.READ_CONTROL)
                try:
                    w.validate_acl(handle,out.sid);identity=native_id(handle)
                    for offset in range(0,len(data),65536):
                        budget();chunk=data[offset:offset+65536];count=w.W.DWORD()
                        w.check(w.write_file(handle,chunk,len(chunk),C.byref(count),None))
                        if count.value!=len(chunk):raise OSError('PARTIAL_INSTALLATION_PRESERVED')
                        charged+=count.value
                    w.check(w.flush(handle));info=w.info(handle)
                    if native_id(handle)!=identity or info.links!=1 or (info.size_hi<<32|info.size_lo)!=len(data):
                        raise ValueError('CREATION_HANDLE_IDENTITY_CHANGED')
                finally:close_native(handle)
                result['files'].append({'path':name,'bytes':len(data),'sha256':row['sha256'],'id':identity})
                if index%250==0:notify()
                if interrupt_after==index+1:raise OSError('EXPLICIT_SYNTHETIC_INTERRUPTION')
            # Independent post-copy native reads, not merely copied-source hashes.
            for row in result['files']:
                budget();relative=Path(row['path']);out=targets[relative.parent.as_posix()]
                handle=open_native(out.root_handle,relative.name,out.sid,False,access=w.READ|w.READ_CONTROL)
                try:
                    w.validate_acl(handle,out.sid);info=w.info(handle)
                    if native_id(handle)!=row['id'] or info.links!=1:raise ValueError('READBACK_IDENTITY')
                    checksum=hashlib.sha256();length=0
                    while True:
                        budget();buf=C.create_string_buffer(65536);count=w.W.DWORD()
                        w.check(w.read_file(handle,buf,65536,C.byref(count),None))
                        if not count.value:break
                        checksum.update(buf.raw[:count.value]);length+=count.value
                        if length>row['bytes']:raise ValueError('READBACK_GROWTH')
                    if length!=row['bytes'] or checksum.hexdigest()!=row['sha256']:raise ValueError('READBACK_CONTENT')
                finally:close_native(handle)
            _verify_namespace(destination,{r['path'] for r in result['files']},
                {r['path'] for r in result['directories']},budget)
            result['status']='NATIVE_COPY_ACL_IDENTITY_HASH_VERIFIED_UNSELECTED'
    except BaseException as error:
        result.update(status='REFUSED_PRESERVE_PARTIAL',error_type=type(error).__name__,reason=str(error));raise
    finally:
        remaining=len(open_files)+sum(len(out.handles) for out in [*targets.values(),*readers.values()])
        bundle.close();result.update(seconds=round(time.monotonic()-started,3),charged_bytes=charged,
            retained_handles_after_close=remaining);notify()
    return result
