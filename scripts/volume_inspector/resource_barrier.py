"""Single-use synthetic NTFS file lease, NOT a directory/volume/writer fence.

Demonstrates ordinary-open exclusion on one exact file. Does not establish
absence of mapped views, privileged writers or Linux container activity.
No production admission/recovery/initialization or Docker interface.
"""
import copy
import ctypes as C
import importlib.util
import secrets
from pathlib import Path

spec = importlib.util.spec_from_file_location('barrier_snapshot', Path(__file__).with_name('snapshot_store.py'))
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
w, Refused = s.w, s.Refused


class FileLease:
    def __init__(self, root, pin, phase, fixture):
        if phase not in ('INSPECTION', 'RECOVERY') or fixture != {
                'source': 'SYNTHETIC', 'helper': 'EXITED', 'identity': 'MATCH',
                'docker': 'AVAILABLE', 'external_writer': 'NONE'}:
            raise Refused('Synthetic exact/quiescent facts required; no production proof')
        self.output, self.handle, self.token = w.WindowsOutput(root), None, None
        try:
            self.output._verify()
            if s.native.file_identity(self.output.root_handle) != pin['root_id']:
                raise Refused('Resource root replaced')
            self.token = {'nonce': secrets.token_hex(16), 'owner': s.native.current_process_identity(),
                          'phase': phase, 'pin': copy.deepcopy(pin), 'scope': 'SYNTHETIC_ONE_FILE'}
            # Never reset or reuse a previous intent, even if the owning process died.
            self.output._write(self.output.root_handle, 'barrier-intent.json', s.encoded(self.token))
            leaf = 'resource.json'
            text = C.create_unicode_buffer(leaf)
            name = w.Unicode(len(leaf.encode('utf-16-le')), C.sizeof(text), C.cast(text, w.W.LPWSTR))
            attributes = w.ObjectAttributes(C.sizeof(w.ObjectAttributes), self.output.root_handle,
                                            C.pointer(name), 0x40 | 0x1000, None, None)
            handle = w.W.HANDLE()
            # NtCreateFile relative/no-follow, ShareAccess=0, synchronous regular file.
            w.nt_check(w.nt_create(C.byref(handle), w.READ | w.READ_CONTROL | w.SYNC,
                                  C.byref(attributes), C.byref(w.IO()), None, 0, 0, 1,
                                  0x200000 | 0x20 | 0x40, None, 0))
            self.handle = handle
            w.validate_acl(handle, self.output.sid)
            self.assert_held(self.token)
        except BaseException:
            self.close()
            raise

    def assert_held(self, token):
        if self.handle is None or s.encoded(token) != s.encoded(self.token):
            raise Refused('Released/stale/foreign lease')
        if token['owner'] != s.native.current_process_identity():
            raise Refused('Lease process identity changed')
        info = w.info(self.handle)
        if info.links != 1 or info.attributes & (0x400 | 0x10) or s.native.file_identity(self.handle) != token['pin']['file']['id']:
            raise Refused('File identity/link/type changed')
        size = (info.size_hi << 32) | info.size_lo
        if size > 4096:
            raise Refused('Synthetic file size limit')
        seek = w.bind(w.K, 'SetFilePointerEx', [w.W.HANDLE, C.c_longlong, C.c_void_p, w.W.DWORD])
        w.check(seek(self.handle, 0, None, 0))
        buf, count = C.create_string_buffer(4097), w.W.DWORD()
        w.check(w.read_file(self.handle, buf, 4097, C.byref(count), None))
        if count.value != size or s.sha(buf.raw[:count.value]) != token['pin']['file']['sha256']:
            raise Refused('File content changed under lease')
        return {'scope': 'ONE_FILE_ORDINARY_OPEN_EXCLUSION', 'production_recovery': False}

    def release(self, token):
        self.assert_held(token)
        self.output._write(self.output.root_handle, 'release-intent.json', s.encoded(token))
        w.close_handle(self.handle)
        self.handle = None
        self.output._write(self.output.root_handle, 'released.json', b'{"released":true,"startup_permission":false}')

    def close(self):
        if self.handle is not None:
            w.close_handle(self.handle)
            self.handle = None
        if self.output:
            self.output.close()
            self.output = None

    def production_recovery(self):
        raise Refused('One NTFS file is not all-writer or helper quiescence proof')
