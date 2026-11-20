"""Bounded loopback diagnostics: complete HTTP response AND actual TCP peer EOF."""

import ipaddress
import socket
from http.client import HTTPResponse


def probe(*, port, path, method="GET", timeout=3, maximum_bytes=1024 * 1024):
    if (
        type(port) is not int
        or not 1 <= port <= 65535
        or type(path) is not str
        or not path.startswith("/")
        or not path.isascii()
        or any(ord(c) <= 32 or ord(c) >= 127 for c in path)
        or method not in ("GET", "POST")
        or type(timeout) not in (int, float)
        or not 0 < timeout <= 3
        or type(maximum_bytes) is not int
        or not 0 < maximum_bytes <= 1024 * 1024
    ):
        raise ValueError("BOUNDED_EXACT_LOOPBACK_PROBE_REQUIRED")
    # Keep the original socket handle until actual peer EOF. HTTPResponse.close
    # closes only its makefile; a Content-Length read alone is not TCP teardown.
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as sock:
        if not ipaddress.ip_address(sock.getpeername()[0]).is_loopback:
            raise ValueError("LOOPBACK_PEER_REQUIRED")
        sock.sendall(
            (
                f"{method} {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
                "Connection: close\r\nContent-Length: 0\r\n\r\n"
            ).encode("ascii")
        )
        with HTTPResponse(sock) as response:
            response.begin()
            if not response.will_close:
                raise ValueError("PEER_DID_NOT_AGREE_TO_CLOSE")
            data = response.read(maximum_bytes + 1)
            if len(data) > maximum_bytes or response.length not in (None, 0):
                raise ValueError("HTTP_RESPONSE_INCOMPLETE_OR_CAPACITY")
            status, headers = response.status, dict(response.getheaders())
        if sock.recv(1) != b"":
            raise ValueError("TCP_PEER_EOF_NOT_VERIFIED")
        sock.shutdown(socket.SHUT_WR)
    return {
        "status": status,
        "headers": headers,
        "data": data,
        "peer_eof": True,
        "client_handle_closed": True,
    }
