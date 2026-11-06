"""Injected-only original owner case-host launch-intent checks; no native launch."""

import pytest

from scripts.observation_runtime.aip06_case_host_entry import HOST_ENTRY
from scripts.observation_runtime.aip06_case_host_launch_intent import inspect_launch_intent
from test_aip06_scoped_context import in_controller, intent


def test_case_host_launch_intent_requires_pinned_target(monkeypatch):
    def check(t):
        case = t.factory.create(intent(t), deadline_ns=t.x.now[0]+10**9)
        ticket = case.reserve(deadline_ns=t.x.now[0]+10**9)
        with pytest.raises(ValueError, match='PINNED_NATIVE_CASE_HOST_TARGET_REQUIRED'):
            inspect_launch_intent(case, ticket, deadline_ns=t.x.now[0]+10**9)
        assert case.abort(ticket, deadline_ns=t.x.now[0]+10**9)
    in_controller(monkeypatch, check)


def test_case_host_launch_intent_uses_original_held_reservation(monkeypatch):
    def check(t):
        case = t.factory.create(intent(t), deadline_ns=t.x.now[0]+10**9)
        ticket = case.reserve(deadline_ns=t.x.now[0]+10**9)
        with pytest.raises(ValueError, match='ORIGINAL_HELD_CASE_RESERVATION_FOR_HOST_LAUNCH'):
            inspect_launch_intent(case, dict(ticket, held=False), deadline_ns=t.x.now[0]+10**9)
        # A late controller target mutation cannot qualify the original graph.
        original_targets = dict(t.controller.profile['targets'])
        t.controller.profile['targets']['case_host'] = HOST_ENTRY
        with pytest.raises(ValueError, match='CURRENT_CONTROLLER_GRAPH_AND_IMMUTABLE_DESCRIPTOR'):
            inspect_launch_intent(case, ticket, deadline_ns=t.x.now[0]+10**9)
        t.controller.profile['targets'] = original_targets
        assert case.abort(ticket, deadline_ns=t.x.now[0]+10**9)
    in_controller(monkeypatch, check)
