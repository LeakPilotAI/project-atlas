"""Explicitly bounded observation HTTP transport; no financial/provider capabilities.

A request attempt is an accepted TCP connection, conservatively charged before
HTTP parsing. HTTP/1.0 closes each connection after one request. Connections not
accepted after listener closure are not HTTP requests received by this host.
"""
import socket
import threading
import time
from http.server import HTTPServer


class BoundedHTTPServer(HTTPServer):
    allow_reuse_address = False

    def __init__(self, address, handler, *, limit, seconds=180):
        if type(limit) is not int or not 1 <= limit <= 96:
            raise ValueError('EXACT_REQUEST_CEILING_REQUIRED')
        if not 0 < seconds <= 180:
            raise ValueError('BOUNDED_OBSERVATION_DEADLINE_REQUIRED')
        self.limit = limit
        self.deadline = time.monotonic() + seconds
        self.timeout = .05
        self._stop = threading.Event()
        self._closed = threading.Event()
        self._lock = threading.Lock()
        self._counts = dict(total_attempted=0, admitted=0, rejected=0, pending=0)
        self._status = None
        super().__init__(address, handler)

    def server_bind(self):
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def get_request(self):
        connection, address = super().get_request()
        with self._lock:
            if self._counts['total_attempted'] >= self.limit:
                connection.close()
                raise RuntimeError('BUDGET_INVARIANT_VIOLATION')
            self._counts['total_attempted'] += 1
            self._counts['pending'] += 1
        connection.settimeout(max(.001, min(2, self.deadline - time.monotonic())))
        return connection, address

    def finish_request(self, request, address):
        # Serial transport is deliberate: no N+1 accept/worker race at the cap.
        self._status = None
        failed = True
        try:
            super().finish_request(request, address)
            failed = False
        finally:
            with self._lock:
                admitted = not failed and self._status is not None and 200 <= self._status < 400
                self._counts['admitted' if admitted else 'rejected'] += 1
                self._counts['pending'] -= 1

    def record_status(self, status):
        self._status = status

    def counts(self):
        with self._lock:
            return dict(self._counts)

    def serve_forever(self, poll_interval=.05):
        try:
            while not self._stop.is_set() and time.monotonic() < self.deadline:
                if self.counts()['total_attempted'] >= self.limit:
                    break
                self.handle_request()
        finally:
            self.server_close()
            self._closed.set()

    def shutdown(self):
        self._stop.set()
        if not self._closed.wait(3):
            raise RuntimeError('BOUNDED_HOST_SHUTDOWN_UNCONFIRMED')
