import os,json,time
from pathlib import Path
_live_root=Path(__file__).parent
if not os.environ.get('ATLAS_AUTH_SCOPE_SHA256') or not (_live_root/'single-use-claim.json').exists():
    raise SystemExit('NO_LIVE_EXPLICITLY_APPROVED_ACCEPTANCE_SESSION')
_live=json.loads((_live_root/'single-use-claim.json').read_bytes())
assert _live['scope_sha256']==os.environ['ATLAS_AUTH_SCOPE_SHA256'] and time.perf_counter_ns()<_live['deadline_ns']
import ctypes
from pathlib import Path
import json
import sys
import time

out = Path(__file__).parent
root = Path(r'D:\AtlasRuntime\releases\2c039af29dfefd1df77e0caa3db3fdf5ed188118')
assert Path(sys.executable) == root / 'python/python.exe'
sys.path[:0] = [str(root / 'backend'), str(root)]
from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock, _WindowsProbe, parse_status

# Ordinary Windows token only: never request UAC or mutate clock/service state.
assert not ctypes.windll.shell32.IsUserAnAdmin(), 'DIAGNOSTIC_REQUIRES_ORDINARY_PROCESS'
started = time.perf_counter()
deadline = started + 180
rows = []
while time.perf_counter() + 28 < deadline:
    clock = None
    row = {'index': len(rows) + 1, 'started_utc_ns': time.time_ns(), 'accepted': False}
    try:
        runtime = 'qd-final-preflight-clock-' + str(row['index'])
        clock = LocalWindowsClock(expected_source='time.windows.com,0x9', runtime_id=runtime)
        clock.require_operational(runtime)
        row.update(accepted=True, bound_ms=clock.evidence['bound_ms'], evidence=clock.evidence)
    except Exception as exc:
        row.update(error_type=type(exc).__name__, error=str(exc))
        if str(exc).startswith('CLOCK_UNCERTAINTY_EXCEEDED:'):
            row['bound_ms'] = int(str(exc).split(':', 1)[1][:-2])
    finally:
        if clock is not None:
            clock.revoke()
            row['capability_revoked'] = True
    # Separate genuine OS observation for detailed diagnostics on refusals.
    # This is never injected into operational clock construction or accepted
    # as an alternate operational authority.
    try:
        row['following_query_utc_ns'] = time.time_ns()
        raw = _WindowsProbe().read()
        row['following_os_observation'] = raw
        row['following_status'] = parse_status(raw['status'])
    except Exception as exc:
        row['following_query_error'] = str(exc)
    row['finished_utc_ns'] = time.time_ns()
    row['elapsed_seconds'] = time.perf_counter() - started
    rows.append(row)
    (out / ('observation-' + str(row['index']) + '.json')).write_text(json.dumps(row, indent=2))
    print(json.dumps({k: row[k] for k in ('index', 'accepted', 'bound_ms', 'error', 'following_status', 'elapsed_seconds') if k in row}), flush=True)
    if row['accepted']:
        break
    if row.get('error') not in ('CLOCK_UNSYNCHRONIZED', 'CLOCK_STALE_OR_NEGATIVE_QUALITY') and not row.get('error', '').startswith('CLOCK_UNCERTAINTY_EXCEEDED:'):
        break
    if time.perf_counter() + 58 >= deadline:
        break
    time.sleep(30)
summary = {'accepted': any(row['accepted'] for row in rows), 'observations': len(rows),
           'initial_bound_ms': rows[0].get('bound_ms') if rows else None,
           'final_bound_ms': rows[-1].get('bound_ms') if rows else None,
           'lowest_bound_ms': min((row['bound_ms'] for row in rows if 'bound_ms' in row), default=None),
           'bound_trend_ms': [row.get('bound_ms') for row in rows],
           'elapsed_seconds': time.perf_counter() - started,
           'all_created_capabilities_revoked': all(row.get('capability_revoked', True) for row in rows),
           'administrator': False}
assert summary['elapsed_seconds'] <= 180
(out / 'summary.json').write_text(json.dumps(summary, indent=2))
print(json.dumps(summary), flush=True)
sys.exit(0 if summary['accepted'] else 2)
