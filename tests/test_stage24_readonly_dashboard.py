"""Real loopback transport with synthetic static bytes; no protected services."""
import json
import socket
import threading
import unittest
from http.client import HTTPConnection

from scripts.observation_runtime.readonly_dashboard import (
    MEMBERS,
    make_host,
    verify_ready,
)


class DashboardTests(unittest.TestCase):
    def test_idle_browser_connection_cannot_block_shutdown(self):
        client = socket.create_connection(self.server.server_address, timeout=2)
        client.sendall(b"GET / HTTP/1.1\r\n")
        import time
        time.sleep(0.1)
        shutdown = threading.Thread(target=self.server.shutdown)
        shutdown.start()
        try:
            shutdown.join(2)
            self.assertFalse(shutdown.is_alive(), "Idle HTTP client blocks graceful shutdown")
        finally:
            client.close()
            shutdown.join(3)

    def setUp(self):
        self.assets = {"/" + name: b"fixture" for name in MEMBERS}
        self.server = make_host(self.assets)
        self.worker = threading.Thread(target=self.server.serve_forever)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(3)

    def request(self, path, method="GET", host=None):
        conn = HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        conn.request(method, path, headers={} if host is None else {"Host": host})
        result = conn.getresponse()
        status, body = result.status, result.read()
        conn.close()
        return status, body

    def test_loopback_and_readiness(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        self.assertTrue(verify_ready(self.server).startswith("http://127.0.0.1:"))

    def test_disabled_state(self):
        status, body = self.request("/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["backend"], "UNAVAILABLE")

    def test_traversal_and_protected_routes(self):
        for route in ("/../.env", "/%2e%2e/.env", "/manifest.json", "/api/orders", "/", "/missing"):
            self.assertEqual(self.request(route)[0], 200 if route == "/" else 404)

    def test_foreign_host_and_mutation(self):
        self.assertEqual(self.request("/", host="foreign.example")[0], 403)
        self.assertEqual(self.request("/", method="POST")[0], 501)

    def test_port_collision_refused(self):
        with self.assertRaises(OSError):
            other = make_host(self.assets, self.server.server_port)
            other.server_close()

    def test_snapshot_and_missing_assets(self):
        self.assets["/index.html"] = b"replacement"
        self.assertEqual(self.request("/")[1], b"fixture")
        with self.assertRaises(ValueError):
            make_host({})

    def test_identity_mismatch(self):
        self.server.host_id = "foreign"
        with self.assertRaises(RuntimeError):
            verify_ready(self.server)

    def test_shutdown_releases_only_host_port(self):
        unrelated = socket.socket()
        unrelated.bind(("127.0.0.1", 0))
        try:
            self.server.shutdown()
            self.assertGreater(unrelated.getsockname()[1], 0)
        finally:
            unrelated.close()
