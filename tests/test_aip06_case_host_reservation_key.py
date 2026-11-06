"""Malformed reservation keys must fail closed before ledger lookup."""
import copy
from types import SimpleNamespace

import pytest

from scripts.observation_runtime import aip06_scoped_context as scoped


@pytest.mark.parametrize('key', [None, '', [], {}, 7, True], ids=['none', 'empty', 'list', 'dict', 'integer', 'boolean'])
def test_host_handoff_refuses_invalid_reservation_key(monkeypatch, key):
    view = {'owner': 'owner', 'intent': {'scenario': 'F01', 'case': 'case',
            'manifest': 'manifest', 'evidence': 'evidence', 'commands': (('worker', ('python', '-B', 'worker.py')),),
            'root': 'case-root'}}
    monkeypatch.setattr(scoped, 'verify_inherited_scope', lambda packet, descriptor: copy.deepcopy(view))
    monkeypatch.setattr(scoped, 'contracts', lambda: [SimpleNamespace(id='F01', roles=('worker',))])
    ticket = {'scenario': 'F01', 'root': scoped.ROOTS['E'], 'roles': ('worker',),
              'held': True, 'stop_capacity_reserved': True, 'key': key,
              'commands': dict(view['intent']['commands']), 'controller_command': ('python', '-B', 'controller.py'),
              'case': 'case', 'manifest': 'manifest', 'evidence': 'evidence'}
    packet = {'schema': 'AIP06_PHYSICAL_CASE_HOST_HANDOFF_V1', 'case': {},
              'reservation': ticket, 'native_acceptance': False}
    packet['integrity'] = scoped.digest(packet)
    guard = SimpleNamespace(resources=SimpleNamespace(channel=SimpleNamespace(
        binding={'launch': {'command': ticket['controller_command']}})))
    with pytest.raises(ValueError, match='EXACT_PHYSICAL_HOST_RESERVATION_SCOPE'):
        scoped.verify_physical_host_handoff(packet, {}, guard)
