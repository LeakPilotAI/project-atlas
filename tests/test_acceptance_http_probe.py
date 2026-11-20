"""Offline peer-EOF barrier: no actual network or installed runtime."""

import io
import socket

import pytest

from scripts.observation_runtime import acceptance_http_probe as module


class FakeSocket:
    def __init__(self, wire, trailing=b""):
        self.wire, self.trailing, self.events = wire, trailing, []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.events.append("CLIENT_HANDLE_CLOSED")

    def getpeername(self):
        return "127.0.0.1", 42100

    def sendall(self, data):
        assert b"Connection: close\r\n" in data
        self.events.append("REQUEST")

    def makefile(self, *_args):
        self.events.append("HTTP_PARSE")
        return io.BytesIO(self.wire)

    def recv(self, count):
        assert count == 1
        self.events.append("PEER_EOF_READ")
        return self.trailing

    def shutdown(self, how):
        assert how == socket.SHUT_WR
        self.events.append("FIN")


def test_content_length_completion_is_followed_by_actual_eof_then_owned_close(
    monkeypatch,
):
    fake = FakeSocket(
        b"HTTP/1.1 200 OK\r\nConnection: close\r\nContent-Length: 2\r\n\r\nok"
    )
    monkeypatch.setattr(module.socket, "create_connection", lambda *_a, **_k: fake)
    value = module.probe(port=42100, path="/dashboard")
    assert (
        value["data"] == b"ok" and value["peer_eof"] and value["client_handle_closed"]
    )
    assert fake.events == [
        "REQUEST",
        "HTTP_PARSE",
        "PEER_EOF_READ",
        "FIN",
        "CLIENT_HANDLE_CLOSED",
    ]


@pytest.mark.parametrize("case", ["trailing", "short", "oversize", "keepalive"])
def test_no_success_without_complete_bounded_response_and_tcp_eof(monkeypatch, case):
    wire = b"HTTP/1.1 200 OK\r\nConnection: close\r\nContent-Length: 2\r\n\r\nok"
    if case == "short":
        wire = wire[:-1]
    elif case == "oversize":
        wire = wire.replace(b"Length: 2", b"Length: 20") + b"x" * 18
    elif case == "keepalive":
        wire = wire.replace(b"close", b"keep-alive")
    fake = FakeSocket(wire, trailing=b"x" if case == "trailing" else b"")
    monkeypatch.setattr(module.socket, "create_connection", lambda *_a, **_k: fake)
    with pytest.raises(ValueError):
        module.probe(port=42100, path="/", maximum_bytes=10)
    assert fake.events[-1] == "CLIENT_HANDLE_CLOSED"
    assert "FIN" not in fake.events


@pytest.mark.parametrize(
    "extra",
    [
        {"port": 0},
        {"path": "/\r\nforeign"},
        {"method": "DELETE"},
        {"maximum_bytes": 0},
        {"timeout": 4},
    ],
)
def test_invalid_probe_refuses_before_socket_creation(monkeypatch, extra):
    monkeypatch.setattr(
        module.socket, "create_connection", lambda *_a, **_k: pytest.fail("socket")
    )
    values = {"port": 42100, "path": "/"}
    values.update(extra)
    with pytest.raises(ValueError):
        module.probe(**values)
