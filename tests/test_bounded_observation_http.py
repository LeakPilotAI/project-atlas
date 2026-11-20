"""Synthetic-only real loopback budget regression; no retained journal access."""
import concurrent.futures
import http.client
import socket
import threading

import pytest

from scripts.observation_runtime.desktop_observation import make_host


class SyntheticSession:
    def snapshot(self):
        return {}


def start(limit):
    host, _ = make_host(SyntheticSession(), request_limit=limit, deadline_seconds=5)
    port = host.server_port
    worker = threading.Thread(target=host.serve_forever)
    worker.start()
    return host, port, worker


def request(port, path='/health', method='GET', foreign=False):
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
    try:
        connection.request(method, path, headers={'Host': 'foreign.invalid'} if foreign else {})
        response = connection.getresponse()
        response.read()
        return response.status
    finally:
        connection.close()


def released(host, port, worker):
    host.shutdown()
    worker.join(3)
    assert not worker.is_alive()
    with socket.socket() as probe:
        assert probe.connect_ex(('127.0.0.1', port)) != 0
    counts = host.counts()
    assert counts['pending'] == 0
    assert counts['total_attempted'] == counts['admitted'] + counts['rejected']
    return counts


def test_rejected_requests_consume_ceiling_and_listener_closes_at_limit():
    host, port, worker = start(4)
    try:
        assert request(port) == 200
        assert request(port, foreign=True) == 403
        assert request(port, '/absent') == 404
        assert request(port, method='POST') == 403
        worker.join(3)  # No fifth limit-triggering request is needed.
        assert not worker.is_alive()
    finally:
        counts = released(host, port, worker)
    assert counts == dict(total_attempted=4, admitted=1, rejected=3, pending=0)


@pytest.mark.parametrize('payload', [b'NOT HTTP\r\n\r\n', b''])
def test_malformed_or_abandoned_connection_is_counted(payload):
    host, port, worker = start(1)
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=3) as client:
            client.sendall(payload)
            client.shutdown(socket.SHUT_WR)
            while client.recv(1024):
                pass
        worker.join(3)
    finally:
        counts = released(host, port, worker)
    assert counts == dict(total_attempted=1, admitted=0, rejected=1, pending=0)


def test_concurrent_rejections_cannot_extend_budget():
    host, port, worker = start(8)
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            statuses = list(pool.map(lambda _: request(port, method='POST'), range(8)))
        assert statuses == [403] * 8
        worker.join(3)
    finally:
        counts = released(host, port, worker)
    assert counts == dict(total_attempted=8, admitted=0, rejected=8, pending=0)


@pytest.mark.parametrize('limit', [0, 97, True, 1.5])
def test_invalid_budget_refused_before_listener(limit):
    with pytest.raises(ValueError, match='CEILING'):
        make_host(SyntheticSession(), request_limit=limit)


def test_full_96_request_ceiling_includes_every_refusal():
    host, port, worker = start(96)
    try:
        for _ in range(96):
            assert request(port, method='POST') == 403
        worker.join(3)
        assert not worker.is_alive()
        with pytest.raises(OSError):
            request(port)
    finally:
        counts = released(host, port, worker)
    assert counts == dict(total_attempted=96, admitted=0, rejected=96, pending=0)
