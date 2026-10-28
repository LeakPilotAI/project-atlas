"""Existing immutable release inventory, pinned by original native read handles.

Uses the established installation receipt format. No installer, issuer, source
rewriter or default release. Same-user custody is not independent security trust.
"""
import ctypes as C
import hashlib
import os
import re
import sys
import time
from pathlib import Path, PurePosixPath

from app.services.paper_financial_replay import body, digest, strict

from scripts.observation_runtime.personal_paper_inception import native_primitives
from scripts.observation_runtime.quality_dips_read_service import observe_self


class NativePersonalReleaseIdentity:
    def __init__(self, *, receipt=None, artifact_digest=None):
        if (type(receipt) is not dict or receipt.get('schema') != 'ATLAS_QD_D_RUNTIME_INSTALLATION_V1'
                or receipt.get('stage') != 'D_RUNTIME_LAYOUT_VERIFIED'
                or type(artifact_digest) is not str or not re.fullmatch('[0-9a-f]{64}', artifact_digest)
                or type(receipt.get('source_commit')) is not str or not re.fullmatch('[0-9a-f]{40}', receipt['source_commit'])
                or type(receipt.get('files')) is not list or not 1 <= len(receipt['files']) <= 40000
                or type(receipt.get('directories')) is not list or not 1 <= len(receipt['directories']) <= 1024):
            raise ValueError('PERSONAL_RELEASE_VERIFIED_INVENTORY_REQUIRED')
        self.receipt = strict(body(receipt))
        self.root = Path(receipt['release_path'])
        expected = Path('D:/AtlasRuntime/releases')/receipt['source_commit']
        if self.root != expected or digest(receipt['files']) != artifact_digest:
            raise ValueError('PERSONAL_RELEASE_PATH_OR_ARTIFACT')
        self.artifact_digest, self.source_commit = artifact_digest, receipt['source_commit']
        self._config = body(self.receipt), self.root, artifact_digest
        self.native = native_primitives()
        self.outputs, self.handles, self.files = {}, {}, {}
        self.closed = False
        start, total = time.monotonic(), 0
        try:
            for directory in receipt['directories']:
                self._native_id(directory['id'])
                value = Path(directory['path'])
                relative = str(value.relative_to(self.root)) if value.is_absolute() else str(value)
                relative = self._relative(relative, directory=True)
                if relative.casefold() in self.outputs:
                    raise ValueError('PERSONAL_RELEASE_DIRECTORY_ALIAS')
                output = self.native.w.WindowsOutput(str(self.root/relative))
                self.outputs[relative.casefold()] = output
                if self.native.native.file_identity(output.root_handle) != directory['id']:
                    raise ValueError('PERSONAL_RELEASE_DIRECTORY_SUBSTITUTION')
                if time.monotonic()-start > 180:
                    raise ValueError('PERSONAL_RELEASE_VERIFICATION_DEADLINE')
            if '.' not in self.outputs:
                raise ValueError('PERSONAL_RELEASE_ROOT_NOT_ENROLLED')
            for item in receipt['files']:
                self._native_id(item['id'])
                name = self._relative(item['path'])
                key = name.casefold()
                if (key in self.handles or type(item['bytes']) is not int or item['bytes'] < 0
                        or total+item['bytes'] > 1024**3 or not re.fullmatch('[0-9a-f]{64}', item['sha256'])):
                    raise ValueError('PERSONAL_RELEASE_FILE_ALIAS_OR_CAPACITY')
                relative = Path(name)
                out = self.outputs[str(relative.parent).casefold()]
                handle = self.native.w.relative_open(out.root_handle, relative.name, out.sid, False,
                                                     access=self.native.w.READ | self.native.w.READ_CONTROL)
                self.handles[key] = handle
                self.native.w.validate_acl(handle, out.sid)
                info = self.native.w.info(handle)
                if (self.native.native.file_identity(handle) != item['id'] or info.links != 1
                        or ((info.size_hi << 32) | info.size_lo) != item['bytes']):
                    raise ValueError('PERSONAL_RELEASE_FILE_SUBSTITUTION')
                checksum, count = hashlib.sha256(), 0
                while True:
                    if time.monotonic()-start > 180:
                        raise ValueError('PERSONAL_RELEASE_VERIFICATION_DEADLINE')
                    buffer, read = C.create_string_buffer(65536), self.native.w.W.DWORD()
                    self.native.w.check(self.native.w.read_file(handle, buffer, 65536, C.byref(read), None))
                    if not read.value:
                        break
                    count += read.value
                    if count > item['bytes']:
                        raise ValueError('PERSONAL_RELEASE_FILE_GROWTH')
                    checksum.update(buffer.raw[:read.value])
                if count != item['bytes'] or checksum.hexdigest() != item['sha256']:
                    raise ValueError('PERSONAL_RELEASE_CONTENT_MISMATCH')
                self.files[key] = strict(body(item))
                total += count
            # Refuse unlisted files, unknown directories and reparse points.
            actual_files, actual_dirs = set(), {'.'}
            for parent, dirs, files in os.walk(self.root, followlinks=False):
                if time.monotonic()-start > 180:
                    raise ValueError('PERSONAL_RELEASE_VERIFICATION_DEADLINE')
                for leaf in dirs+files:
                    path = Path(parent)/leaf
                    if path.is_symlink() or path.is_junction():
                        raise ValueError('PERSONAL_RELEASE_REPARSE')
                    key = str(path.relative_to(self.root)).casefold()
                    if key not in (self.outputs if leaf in dirs else self.files):
                        raise ValueError('PERSONAL_RELEASE_UNLISTED_NAMESPACE')
                    (actual_dirs if leaf in dirs else actual_files).add(key)
            if actual_files != set(self.files) or actual_dirs != set(self.outputs):
                raise ValueError('PERSONAL_RELEASE_INCOMPLETE_INVENTORY')
            self._process = observe_self()
            self._ports = self.native, tuple(self.outputs.items()), tuple(self.handles.items())
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _native_id(value):
        if type(value) is not list or len(value) != 3 or any(type(v) is not int or v < 0 for v in value):
            raise ValueError('PERSONAL_RELEASE_NATIVE_ID')

    @staticmethod
    def _relative(value, *, directory=False):
        if type(value) is not str:
            raise ValueError('PERSONAL_RELEASE_RELATIVE_PATH')
        value = value.replace('\\','/')
        path = PurePosixPath(value)
        if directory and value == '.':
            return '.'
        if (not value or path.is_absolute() or path.as_posix() != value or ':' in value
                or any(part in ('.','..') for part in value.split('/'))):
            raise ValueError('PERSONAL_RELEASE_RELATIVE_PATH')
        return str(Path(value))

    def verify(self, *, release_digest):
        if (self.closed or release_digest != self.artifact_digest
                or (body(self.receipt), self.root, self.artifact_digest) != self._config
                or (self.native, tuple(self.outputs.items()), tuple(self.handles.items())) != self._ports
                or observe_self() != self._process
                or Path(sys.executable) != self.root/'python/python.exe'
                or not Path(__file__).resolve().is_relative_to(self.root)):
            raise ValueError('PERSONAL_RELEASE_NOT_EXECUTING_ACCEPTED_IMAGE')
        self.outputs['.']._verify()
        return {'source_commit':self.source_commit,'artifact_digest':self.artifact_digest,
                'process':dict(self._process),'files':len(self.files),'directories':len(self.outputs)}

    def close(self):
        for handle in self.handles.values():
            self.native.w.close_handle(handle)
        self.handles.clear()
        for output in self.outputs.values():
            output.close()
        self.outputs.clear()
        self.closed = True
