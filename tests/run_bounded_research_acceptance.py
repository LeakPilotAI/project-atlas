"""Owned synthetic host + installed Chrome; never reads retained observations."""
import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/observation_runtime'))
from disposable_host_owner import observe_pid


def main():
    results = []
    for width in (1440, 800):
        started = time.monotonic()
        child = subprocess.Popen([sys._base_executable, str(ROOT / 'tests/qd_research_recovery_host.py')],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, cwd=ROOT)
        ready = None
        try:
            ready = json.loads(child.stdout.readline())
            assert child.pid == ready['pid']
            observed = observe_pid(child.pid)
            assert observed['created'] == ready['creation_filetime'] and observed['image'] == ready['image']
            run = subprocess.run([sys.executable, str(ROOT / 'tests/run_qd_research_chrome.py'),
                                  ready['root'], '--width', str(width)], capture_output=True, text=True, timeout=55)
            root = Path(ready['root'])
            (root / 'acceptance-stdout.txt').write_text(run.stdout)
            (root / 'acceptance-stderr.txt').write_text(run.stderr)
            assert run.returncode == 0, run.stdout + run.stderr
        finally:
            # Retained child stdin only; never kill by name, PID lookup, or port.
            child.stdin.close()
            child.wait(timeout=10)
            if ready:
                root = Path(ready['root'])
                closed = json.loads((root / 'closed.json').read_text())
                counts = closed['request_counts']
                assert child.returncode == 0 and closed['closed']
                assert counts['total_attempted'] == counts['admitted'] + counts['rejected'] <= 96
                assert counts['pending'] == 0
                with socket.socket() as probe:
                    assert probe.connect_ex(('127.0.0.1', urlsplit(ready['url']).port)) != 0
                result = dict(width=width, root=str(root), elapsed_seconds=round(time.monotonic()-started, 3),
                              request_counts=counts, process_exited=True, port_released=True)
                (root / 'bounded-result.json').write_text(json.dumps(result, indent=2))
                results.append(result)
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
