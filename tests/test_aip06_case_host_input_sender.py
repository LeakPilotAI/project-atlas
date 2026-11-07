"""Offline contract tests for original-channel case-host INPUT sender."""
from types import SimpleNamespace
import pytest
from scripts.observation_runtime.aip06_native_session import ChannelSessionProtocol


class Channel:
    def __init__(self):
        self.sent = []

    def send(self, kind, packet, *, deadline_ns):
        self.sent.append((kind, packet, deadline_ns))


def test_authenticated_original_channel_input_only():
    channel = Channel()
    clock = lambda: 100
    protocol = ChannelSessionProtocol(SimpleNamespace(resource_kinds=()), clock, None)
    child = SimpleNamespace(channel=channel)
    packet = {'schema': 'AIP06_PHYSICAL_CASE_HOST_HANDOFF_V1'}
    protocol.send_case_host_input(child, packet, deadline_ns=200)
    assert channel.sent == [('INPUT', packet, 200)]


def test_sender_rejects_foreign_schema_and_expired_deadline():
    channel = Channel()
    protocol = ChannelSessionProtocol(SimpleNamespace(resource_kinds=()), lambda: 100, None)
    child = SimpleNamespace(channel=channel)
    with pytest.raises(ValueError, match='CASE_HOST_INPUT_SCHEMA_REQUIRED'):
        protocol.send_case_host_input(child, {'schema': 'OTHER'}, deadline_ns=200)
    with pytest.raises(ValueError, match='CASE_HOST_INPUT_DEADLINE_EXPIRED'):
        protocol.send_case_host_input(child, {'schema': 'AIP06_PHYSICAL_CASE_HOST_HANDOFF_V1'}, deadline_ns=100)
    assert channel.sent == []
