r"""Read-only Windows desktop runtime sampler; no external dependencies or orders.

Run from repository root after ATLAS.bat: backend\.venv\Scripts\python.exe
scripts/runtime_recovery_soak.py --seconds 1800 --output logs/diagnostics/recovery-soak
"""
import argparse
import ctypes as c
from ctypes import wintypes as w
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time
import urllib.request


class Memory(c.Structure):
    _fields_ = [('cb', w.DWORD), ('faults', w.DWORD)] + [(name, c.c_size_t) for name in
        ('peak_rss', 'rss', 'peak_paged', 'paged', 'peak_nonpaged', 'nonpaged', 'pagefile', 'peak_pagefile', 'private')]


class Process(c.Structure):
    _fields_ = [('size', w.DWORD), ('usage', w.DWORD), ('pid', w.DWORD), ('heap', c.c_size_t),
                ('module', w.DWORD), ('threads', w.DWORD), ('parent', w.DWORD),
                ('priority', w.LONG), ('flags', w.DWORD), ('exe', w.WCHAR * 260)]


kernel = c.WinDLL('kernel32', use_last_error=True)
psapi = c.WinDLL('psapi', use_last_error=True)
kernel.OpenProcess.restype = w.HANDLE
kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
kernel.CreateToolhelp32Snapshot.restype = w.HANDLE
kernel.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
kernel.Process32FirstW.argtypes = [w.HANDLE, c.POINTER(Process)]
kernel.Process32NextW.argtypes = [w.HANDLE, c.POINTER(Process)]
kernel.CloseHandle.argtypes = [w.HANDLE]
kernel.GetProcessTimes.argtypes = [w.HANDLE] + [c.POINTER(w.FILETIME)] * 4
psapi.GetProcessMemoryInfo.argtypes = [w.HANDLE, c.POINTER(Memory), w.DWORD]


def process_stats(pid):
    handle = kernel.OpenProcess(0x410, False, pid)
    if not handle:
        raise ProcessLookupError(pid)
    try:
        memory = Memory(); memory.cb = c.sizeof(memory)
        if not psapi.GetProcessMemoryInfo(handle, c.byref(memory), memory.cb):
            raise c.WinError(c.get_last_error())
        times = [w.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, *(c.byref(x) for x in times)):
            raise c.WinError(c.get_last_error())
        seconds = lambda x: ((x.dwHighDateTime << 32) + x.dwLowDateTime) / 10_000_000
        result = {'private_mb': round(memory.private / 1048576, 2),
                  'rss_mb': round(memory.rss / 1048576, 2),
                  'cpu_seconds': seconds(times[2]) + seconds(times[3]),
                  'process_started_utc': datetime.fromtimestamp(seconds(times[0])-11644473600, timezone.utc).isoformat()}
    finally:
        kernel.CloseHandle(handle)
    snap = kernel.CreateToolhelp32Snapshot(2, 0)
    entry = Process(); entry.size = c.sizeof(entry)
    children = 0
    try:
        found = kernel.Process32FirstW(snap, c.byref(entry))
        while found:
            if entry.pid == pid:
                result['threads'] = int(entry.threads)
            if entry.parent == pid:
                children += 1
            found = kernel.Process32NextW(snap, c.byref(entry))
    finally:
        kernel.CloseHandle(snap)
    result['child_processes'] = children
    return result


def request(path):
    start = time.perf_counter()
    try:
        with urllib.request.urlopen('http://127.0.0.1:8000' + path, timeout=8) as response:
            body = json.load(response)
        return {'path': path, 'ms': round((time.perf_counter()-start)*1000, 3), 'ok': True}, body
    except Exception as exc:
        return {'path': path, 'ms': round((time.perf_counter()-start)*1000, 3), 'ok': False,
                'error': type(exc).__name__}, {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=int, default=1800)
    parser.add_argument('--output', default='logs/diagnostics/recovery-soak')
    args = parser.parse_args()
    prefix = Path(args.output); prefix.parent.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(Path('logs/runtime/runtime.json').read_text(encoding='utf-8-sig'))
    pid = manifest['pid']
    probe, diagnostic = request('/diagnostics/runtime-latency')
    if not probe['ok'] or diagnostic.get('runtime_metrics', {}).get('pid') != pid:
        raise RuntimeError('Atlas server identity does not match the desktop manifest; do not sample a recycled PID')
    header = {'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
              'pid': pid, 'run_id': manifest['run_id'], 'target_seconds': args.seconds,
              'started_at': datetime.now(timezone.utc).isoformat(), 'process': process_stats(pid)}
    prefix.with_suffix('.header.json').write_text(json.dumps(header, indent=2))
    targets = ['/api/live', '/api/perps/manual/board?limit=12', '/api/investments/quality-dips?limit=50',
               '/diagnostics/research', '/api/command-center/summary', '/api/investments/prospective/report']
    start = time.monotonic(); previous = (start, header['process']['cpu_seconds'])
    next_api = next_diagnostics = 0; target_index = 0
    with prefix.with_suffix('.jsonl').open('w', encoding='utf-8') as log:
        while time.monotonic()-start < args.seconds:
            tick = time.monotonic(); elapsed = tick-start
            row = {'elapsed_sec': round(elapsed, 2), 'timestamp': datetime.now(timezone.utc).isoformat()}
            try:
                row['process'] = process_stats(pid)
                row['cpu_one_core_pct'] = round(100*(row['process']['cpu_seconds']-previous[1])/max(.001,tick-previous[0]), 2)
                previous = (tick, row['process']['cpu_seconds'])
            except Exception as exc:
                row['process_error'] = type(exc).__name__
            health, _ = request('/health'); row['requests'] = [health]
            if elapsed >= next_api:
                path = targets[target_index % len(targets)]; target_index += 1; next_api = elapsed+10
                result, body = request(path); row['requests'].append(result)
                row['surface'] = {'path': path, 'refresh': body.get('runtime_refresh'),
                                  'health': body.get('health'), 'updated_at': body.get('updated_at')}
            if elapsed >= next_diagnostics:
                next_diagnostics = elapsed+15
                result, diagnostics = request('/diagnostics/runtime-latency'); row['requests'].append(result)
                row['diagnostics'] = diagnostics
                result, paper = request('/diagnostics/paper-reconciliation'); row['requests'].append(result)
                row['paper'] = paper
            log.write(json.dumps(row, separators=(',', ':'))+'\n'); log.flush()
            time.sleep(max(0, 2-(time.monotonic()-tick)))
    print(json.dumps({'completed_seconds': round(time.monotonic()-start, 2), 'pid': pid, 'output': str(prefix)}), flush=True)


if __name__ == '__main__':
    main()
