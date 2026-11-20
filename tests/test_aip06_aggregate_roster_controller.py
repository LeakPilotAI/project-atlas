"""Aggregate Job roster must retain its independently checked controller."""
from types import SimpleNamespace

import pytest

from scripts.observation_runtime.aip06_native_session import WindowsSessionPort


@pytest.mark.parametrize('members,expected', [
    ({21, 31, 41}, {31, 41}),
    ({21}, set()),
    ({31, 41}, 'refuse'),
    (set(), 'refuse'),
], ids=['controller-and-descendants', 'controller-only',
        'controller-missing', 'empty-roster'])
def test_aggregate_roster_requires_controller_membership(members, expected):
    port = object.__new__(WindowsSessionPort)
    calls = []
    port.aggregate = SimpleNamespace(
        dormant=False, job=90, controller={'pid': 21},
        _controller=lambda: calls.append('controller'))
    port.calls = SimpleNamespace(
        members=lambda job: calls.append(('members', job)) or members)
    if expected == 'refuse':
        with pytest.raises(ValueError, match='AGGREGATE_CONTROLLER_MISSING_FROM_JOB_ROSTER'):
            port.all_members()
    else:
        assert port.all_members() == expected
    assert calls == ['controller', ('members', 90)]
