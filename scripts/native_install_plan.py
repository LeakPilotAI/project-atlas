"""Pure selected-archive/dependency admission shared by code-only installers."""
import hashlib
import io
import json
import re
import time
import zipfile
from pathlib import Path

from scripts.build_release_candidate import (
    source_bytes,
    verify_candidate,
    windows_namespace,
)


def prepare_install_inputs(*, archive, archive_sha256, source_commit, dependency_receipt,
                           dependency_digest, inventory_digest=None, require_tracked=False):
    started = time.monotonic()
    if type(source_commit) is not str or not re.fullmatch('[0-9a-f]{40}', source_commit):
        raise ValueError('EXACT_SOURCE_COMMIT_REQUIRED')
    verified = verify_candidate(archive, expected_sha256=archive_sha256)
    raw = source_bytes(Path(archive).absolute().parent, Path(archive).name, maximum_bytes=64*1024**2)
    if hashlib.sha256(raw).hexdigest() != archive_sha256:
        raise ValueError('ARCHIVE_CHANGED')
    with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
        manifest = json.loads(bundle.read('release-manifest.json'))
    if manifest['head'] != source_commit:
        raise ValueError('SOURCE_COMMIT_MISMATCH')
    runtime = {r['path']: r for r in manifest['files']}
    if require_tracked and any(r.get('git_status') != 'tracked' for r in runtime.values()):
        raise ValueError('TRACKED_SELECTED_RUNTIME_REQUIRED')
    selected = [{k: r[k] for k in ('path','bytes','sha256')} for r in manifest['files']]
    selected_digest = hashlib.sha256(json.dumps(selected, sort_keys=True, separators=(',',':')).encode()).hexdigest()
    if inventory_digest is not None and (type(inventory_digest) is not str or inventory_digest != selected_digest):
        raise ValueError('EXACT_SELECTED_SOURCE_INVENTORY_REQUIRED')
    receipt = json.loads(json.dumps(dependency_receipt, allow_nan=False))
    if (type(receipt) is not dict or receipt.get('schema') != 'ATLAS_QD_D_RUNTIME_INSTALLATION_V1'
            or receipt.get('stage') != 'D_RUNTIME_LAYOUT_VERIFIED'
            or type(receipt.get('source_commit')) is not str or not re.fullmatch('[0-9a-f]{40}', receipt['source_commit'])
            or type(receipt.get('files')) is not list or not 1 <= len(receipt['files']) <= 40000
            or type(receipt.get('directories')) is not list or not 1 <= len(receipt['directories']) <= 1024
            or type(dependency_digest) is not str or not re.fullmatch('[0-9a-f]{64}', dependency_digest)
            or hashlib.sha256(json.dumps(receipt['files'], sort_keys=True, separators=(',',':')).encode()).hexdigest() != dependency_digest):
        raise ValueError('VERIFIED_DEPENDENCY_INVENTORY_REQUIRED')
    source = Path(receipt['release_path'])
    if source != Path('D:/AtlasRuntime/releases') / receipt['source_commit']:
        raise ValueError('DEPENDENCY_RELEASE_IDENTITY')

    def identity(row):
        if (type(row.get('id')) is not list or len(row['id']) != 3
                or any(type(n) is not int or not 0 <= n <= 0xffffffff for n in row['id'])):
            raise ValueError('DEPENDENCY_NATIVE_ID_REQUIRED')

    files = {}; directories = {}; physical = set()
    for row in receipt['files']:
        if type(row) is not dict or set(row) != {'path','bytes','sha256','id'}:
            raise ValueError('DEPENDENCY_FILE_SCHEMA')
        name = row['path']
        if type(name) is not str:
            raise ValueError('DEPENDENCY_FILE_PATH')
        name = name.replace('\\','/'); windows_namespace([name]); identity(row)
        if (name.casefold() in files or type(row['bytes']) is not int or not 0 <= row['bytes'] <= 1024**3
                or type(row['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', row['sha256'])
                or tuple(row['id']) in physical):
            raise ValueError('DEPENDENCY_DUPLICATE_OR_INVALID_FILE')
        physical.add(tuple(row['id'])); files[name.casefold()] = {**row, 'path': name}
    for row in receipt['directories']:
        if type(row) is not dict or set(row) != {'path','id'} or type(row['path']) is not str:
            raise ValueError('DEPENDENCY_DIRECTORY_SCHEMA')
        identity(row); name = row['path'].replace('\\','/')
        if Path(row['path']) == source:
            name = '.'
        if name != '.': windows_namespace([name + '/__directory_probe__'])
        if name.casefold() in directories or tuple(row['id']) in physical:
            raise ValueError('DEPENDENCY_DIRECTORY_ALIAS')
        physical.add(tuple(row['id'])); directories[name.casefold()] = {**row, 'path': name}
    dependencies = {r['path']: r for r in files.values() if r['path'].startswith('python/')}
    if not {'python/python.exe','python/python312.dll','python/Lib/os.py','python/Lib/encodings/__init__.py'} <= set(dependencies):
        raise ValueError('COMPLETE_D_RUNTIME_REQUIRED')
    for name in dependencies:
        for parent in Path(name).parents:
            if parent.as_posix().casefold() not in directories:
                raise ValueError('DEPENDENCY_PARENT_INVENTORY_REQUIRED')
    windows_namespace([r['path'] for r in files.values()] +
                      [r['path']+'/__directory_probe__' for r in directories.values() if r['path'] != '.'])
    names = sorted([*runtime, *dependencies]); windows_namespace(names)
    if len(names) != len(set(names)):
        raise ValueError('DESTINATION_COLLISION')
    target_directories = sorted({p.as_posix() for n in names for p in Path(n).parents if str(p) != '.'},
                                key=lambda p:(len(Path(p).parts),p))
    total = sum(r['bytes'] for r in [*dependencies.values(), *runtime.values()])
    if len(names)+len(target_directories)+1 >= 40000 or total > 1024**3:
        raise ValueError('INSTALL_PLAN_LIMIT')
    return {'raw':raw, 'verified':verified, 'source':source, 'dependencies':dependencies, 'runtime':runtime,
            'names':names, 'directories':target_directories, 'total':total,
            'old_dirs':{r['path']:r for r in directories.values()}, 'selected_digest':selected_digest,
            'started':started}
