"""Actual self-exiting native writers, durable pins and retained Popen handles."""
import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
import test_perp_source_order_native as fixtures

system = fixtures.system
CHILD = Path(__file__).with_name('perp_order_crash_child.py')


def start(path, phase):
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join([str(Path(sys.prefix) / 'Lib/site-packages'), str(CHILD.parents[1] / 'backend')])
    return subprocess.Popen([sys._base_executable, '-B', str(CHILD), '--config', str(path), '--phase', phase],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, creationflags=subprocess.CREATE_NO_WINDOW)


def config(s, order, **extra):
    return {'confinement': str(s.confinement), 'root': str(s.root / 'orders'), 'pin': str(s.order_pins.path),
        'now': s.clock(), 'manifest': s.m, 'event': {'kind': 'ARM', 'order_id': order['order_id'],
            'at': s.clock(), 'payload': order}, 'reservation': {'fixture': 'EXPLICIT_SYNTHETIC'}, **extra}


@pytest.mark.asyncio
@pytest.mark.parametrize('phase', ['before_publication', 'after_record_before_pin', 'after_pin'])
async def test_actual_subprocess_crash_at_native_control_boundaries(system, phase):
    s = system
    order = (await s.planner.next_proposal(None, s.writer._cut()))['order']
    path = s.root / 'crash-config.json'; path.write_text(json.dumps(config(s, order)))
    child = start(path, phase)
    stdout, stderr = child.communicate(timeout=12)
    assert child.returncode == 71, (stdout, stderr)
    assert s.store.verified_cut()['state']['revision'] == 0
    if phase == 'after_record_before_pin':
        with pytest.raises(ValueError): s.orders.snapshot()
    else:
        snapshot = s.orders.snapshot()
        assert snapshot['state']['revision'] == (1 if phase == 'after_pin' else 0)
    # An abandoned writer grants no writable recovery or automatic resumption.
    s.a.control_reservation = {'state': 'RESERVED', 'binding': 'synthetic'}
    with pytest.raises((ValueError, OSError)):
        s.orders.apply({'kind': 'ARM', 'order_id': order['order_id'], 'at': s.clock(), 'payload': order}, s.a.control_reservation)


@pytest.mark.asyncio
async def test_two_native_processes_same_order_have_one_durable_effect(system):
    s = system
    order = (await s.planner.next_proposal(None, s.writer._cut()))['order']
    barrier = s.root / 'go.json'
    children = []
    for index in range(2):
        path, ready = s.root / f'race-{index}.json', s.root / f'ready-{index}.json'
        path.write_text(json.dumps(config(s, order, barrier=str(barrier), ready=str(ready))))
        children.append((start(path, 'none'), ready))
    deadline = time.monotonic() + 8
    while not all(ready.exists() for _, ready in children):
        if time.monotonic() > deadline: raise AssertionError('Test-owned children did not become ready')
        await asyncio.sleep(.01)
    barrier.write_text('GO')
    replies = []
    for child, _ in children:
        stdout, stderr = child.communicate(timeout=12)
        assert child.returncode == 0, stderr
        replies.append(json.loads(stdout))
    assert replies[0] == replies[1]
    assert s.orders.snapshot()['state']['revision'] == 1
    assert s.store.verified_cut()['state']['revision'] == 0


@pytest.mark.asyncio
async def test_missing_pin_or_rollback_refuses_and_never_adopts_tail(system):
    s = system
    p = await s.planner.next_proposal(None, s.writer._cut())
    old = s.order_pins.current()
    s.arm(p)
    s.order_pins.path.write_text(json.dumps(old))  # Explicit disposable coherent-pin rollback probe.
    with pytest.raises(ValueError): s.orders.snapshot()
    s.order_pins.path.write_text('{broken')
    with pytest.raises(ValueError): s.orders.snapshot()
    assert s.store.verified_cut()['state']['revision'] == 0
