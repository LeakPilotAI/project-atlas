"""Explicit bounded browser fixture, actual two-lane native composition; no providers.

Only existing test-confinement env variables are accepted. Native roots are new
children. This is not an operational launcher or an issuer.
"""
import asyncio
import json
import os
import time
import uuid
from pathlib import Path

from test_unified_actual_http import capture, host
from test_unified_actual_native_lanes import cycle
from unified_actual_lanes_fixture import build


def main():
    repo = Path(__file__).resolve().parents[1]
    confinement = Path(os.environ['ATLAS_PERP_ORDER_TEST_ROOT'])
    qdconf = Path(os.environ['ATLAS_UNIFIED_QD_TEST_ROOT'])
    assert confinement.parent == repo / 'logs/diagnostics' and confinement.name.startswith('perp-order-custody-')
    assert qdconf.parent == repo / 'logs/diagnostics' and qdconf.name.startswith('qd-auto-runtime-')
    root = confinement / ('browser-' + uuid.uuid4().hex)
    root.mkdir()
    s = build(root, confinement, qdconf)
    h = ready = None
    try:
        s.r.start({'session_id': 'synthetic-unified-session'})
        asyncio.run(cycle(s))
        h, _ = host(s)
        ready = h.start()
        baseline = capture(s)
        print(json.dumps({'url': ready['url'], 'evidence_root': str(root)}), flush=True)
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline and not (root / 'finish').exists():
            time.sleep(.1)
        after = capture(s)
        after.pop(str(root / 'finish'), None)  # Explicit harness stop signal, never a financial resource.
        assert after == baseline, 'BROWSER_READ_CHANGED_NATIVE_EVIDENCE'
        outcome = s.r.stop()
        (root / 'browser-result.json').write_text(json.dumps({'read_unchanged': True, 'shutdown': outcome}))
    finally:
        if h is not None: h.close(ready)
        s.close()


if __name__ == '__main__':
    main()
