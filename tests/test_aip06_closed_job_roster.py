"""A closed session must not disappear from descendant-roster accounting."""
from types import SimpleNamespace

import pytest

from scripts.observation_runtime.aip06_native_session import WindowsSessionPort


@pytest.mark.parametrize('closed,members,expected', [
    (True, {22}, 'refuse'),
    (True, set(), set()),
    (False, {22}, {22}),
], ids=['closed-with-live-descendant', 'closed-and-empty', 'open-with-descendant'])
def test_roster_rechecks_closed_job_membership(closed, members, expected):
    port = object.__new__(WindowsSessionPort)
    port.aggregate = None
    port.sessions = [SimpleNamespace(job=41, closed=closed)]
    observed = []
    port.calls = SimpleNamespace(members=lambda job: observed.append(job) or members)
    if expected == 'refuse':
        with pytest.raises(ValueError, match='CLOSED_SESSION_JOB_STILL_HAS_DESCENDANTS'):
            port.all_members()
    else:
        assert port.all_members() == expected
    assert observed == [41]
