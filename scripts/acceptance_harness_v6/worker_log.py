"""Publish actual worker log handles; never ownership or execution authority."""

import ctypes as C
import json
import msvcrt
import os
from pathlib import Path

from scripts.observation_runtime.launch_ownership_windows import FileInfo, NativeQueries


def publish_worker_logs(root, stdout, stderr):
    root = Path(root).absolute()
    if any(p.is_symlink() or p.is_junction() for p in (root, *root.parents)):
        raise ValueError("LOG_ROOT_REPARSE")
    launch = json.loads((root / "outer-launch.json").read_bytes())
    native = NativeQueries()
    native.k.GetCurrentProcess.restype = C.c_void_p
    pid, created = native.lifetime(native.k.GetCurrentProcess())
    if pid != launch["pid"] or created != launch["created"]:
        raise ValueError("LOG_ORIGINAL_LAUNCH_IDENTITY_MISMATCH")
    directory = native.k.CreateFileW(str(root), 0x80, 3, None, 3, 0x02200000, None)
    if directory in (None, C.c_void_p(-1).value):
        raise C.WinError(C.get_last_error())
    try:
        info = FileInfo()
        native.check(native.k.GetFileInformationByHandle(directory, C.byref(info)))
        if info.attrs & 0x400 or not info.attrs & 0x10:
            raise ValueError("LOG_ROOT_NATIVE_NAMESPACE")
        root_id = [info.volume, info.index_hi, info.index_lo]
    finally:
        native.check(native.k.CloseHandle(directory))
    files = {}
    for name, stream in (("stdout", stdout), ("stderr", stderr)):
        if Path(stream.name).absolute() != root / f"worker-{name}.log":
            raise ValueError("EXACT_WORKER_LOG_PATH_REQUIRED")
        info = FileInfo()
        h = msvcrt.get_osfhandle(stream.fileno())
        native.check(native.k.GetFileInformationByHandle(h, C.byref(info)))
        born = info.created.dwLowDateTime | info.created.dwHighDateTime << 32
        if info.attrs & 0x410 or info.links != 1 or born < created:
            raise ValueError("LOG_NATIVE_IDENTITY_REQUIRED")
        files[name] = {
            "id": [info.volume, info.index_hi, info.index_lo],
            "created": born,
        }
    packet = {
        "schema": "QD_WORKER_LOG_HANDLES_V6",
        "nonce": launch["nonce"],
        "pid": pid,
        "created": created,
        "root_id": root_id,
        "files": files,
    }
    pending = root / "worker-logs.pending"
    with pending.open("x", encoding="utf-8") as output:
        json.dump(packet, output, separators=(",", ":"))
        output.flush()
        os.fsync(output.fileno())
    # Windows rename refuses replacement; the reader holds the published
    # declaration read-only, without write/delete sharing, until closeout.
    os.rename(pending, root / "worker-logs.json")
    # The marker is created only after rename returns. Readers use its
    # existence as producer completion, then verify the immutable declaration;
    # they never retry a failed declaration/log read into success.
    with (root / "worker-logs.ready").open("xb") as marker:
        marker.write(b"1")
        marker.flush()
        os.fsync(marker.fileno())
    return packet
