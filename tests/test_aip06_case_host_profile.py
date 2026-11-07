"""Controller profile admission for the pinned case host; no native launch."""

import copy
import pytest
from scripts.observation_runtime.aip06_case_host_entry import HOST_ENTRY
from scripts.observation_runtime.aip06_native_controller import NativeController
from test_aip06_windows_adapters import controller_fixture


def test_controller_profile_accepts_only_exact_pinned_case_host():
    f = controller_fixture()
    profile = copy.deepcopy(f.profile)
    profile['source_pins'][HOST_ENTRY] = 'a' * 64
    profile['targets']['case_host'] = HOST_ENTRY
    c = NativeController(files=f.x.calls, process_calls=None, cim_api=None,
                         clock_ns=lambda: f.x.s.now[0], profile=profile)
    assert c.profile['targets']['case_host'] == HOST_ENTRY
    assert not c.initialized and not f.x.calls.events
    profile['targets']['case_host'] = f.path
    with pytest.raises(ValueError, match='ONLY_PINNED_CASE_HOST_TARGET'):
        NativeController(files=f.x.calls, process_calls=None, cim_api=None,
                         clock_ns=lambda: f.x.s.now[0], profile=profile)
    profile['targets']['case_host'] = HOST_ENTRY
    profile['source_pins'].pop(HOST_ENTRY)
    with pytest.raises(ValueError, match='EXACT_CONTROLLER_SOURCE_TARGET_PINS'):
        NativeController(files=f.x.calls, process_calls=None, cim_api=None,
                         clock_ns=lambda: f.x.s.now[0], profile=profile)
