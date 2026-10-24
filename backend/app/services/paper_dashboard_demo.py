"""Unregistered, in-process disposable application. No server or native imports.

The injected verifier must independently derive the supplied summary commitment.
It is a test seam, never a production issuer or authorization mechanism.
"""
import hashlib
from html import escape

from app.services.paper_runtime_boundary import PaperBoundaryRefused, PaperReadOnlyPresentation
from app.services.paper_summary_contract import body


class PaperDashboardDemo:
    def __init__(self, *, boundary=None, verify=None):
        self.boundary, self.verify = boundary, verify
        self.last_failure = None  # Local diagnostic only; never serialized or used as authority.

    def __call__(self, environ, start_response):
        # Reject other verbs/paths before invoking even a read dependency.
        method, path = environ.get("REQUEST_METHOD"), environ.get("PATH_INFO")
        status, content_type = "200 OK", "text/html; charset=utf-8"
        if method != "GET":
            status, output = "405 Method Not Allowed", "Read-only disposable demonstration"
        elif path not in ("/", "/summary.json") or environ.get("QUERY_STRING", ""):
            status, output = "404 Not Found", "No such demonstration resource"
        else:
            try:
                if self.boundary is None or self.verify is None:
                    raise PaperBoundaryRefused("Independent read verification unavailable")
                payload = self.boundary.snapshot()
                encoded = body(payload).encode("utf-8")
                if len(encoded) > 262144:
                    raise PaperBoundaryRefused("Bounded summary required")
                # Pass a copy: verification cannot mutate the rendered snapshot.
                commitment = hashlib.sha256(encoded).hexdigest()
                if self.verify(encoded) != commitment:
                    raise PaperBoundaryRefused("Unverified summary")
                if path == "/summary.json":
                    content_type, output = "application/json; charset=utf-8", encoded.decode("utf-8")
                else:
                    # Reuse Q8 rendering on precisely the verified snapshot; no second read.
                    class FrozenRead:
                        def snapshot(self):
                            return payload
                    table = PaperReadOnlyPresentation(FrozenRead()).html()
                    reasons = "".join("<li>" + escape(row["strategy"] + ": " + ", ".join(row["reason_codes"])) + "</li>"
                                      for row in payload["accounts"])
                    output = ("<!doctype html><html lang=\"en\"><meta charset=\"utf-8\">"
                              "<meta name=\"viewport\" content=\"width=device-width\"><title>Atlas PAPER demo</title>"
                              "<body><main><h1>Atlas · Disposable PAPER accounts</h1>"
                              "<p>Offline test data. No startup, execution or recovery authority.</p>"
                              "<p>Costs combine simulated fees and slippage; separate allocations unavailable. "
                              "Total equity and unrealized P&amp;L unavailable. Freshness refers to financial events, not live quotes.</p>"
                              "<nav><a href=\"/\">Accounts</a> · <a href=\"/summary.json\">Verified summary JSON</a></nav>"
                              + table + "<h2>Evidence notes</h2><ul>" + reasons + "</ul></main></body></html>")
            except (OSError, ValueError, TypeError, KeyError, ArithmeticError, RuntimeError) as error:
                # No stale-success cache and no private exception content in the response.
                self.last_failure = error
                status, output = "503 Service Unavailable", "UNKNOWN — verified evidence unavailable. No startup authority."
        raw = output.encode("utf-8")
        start_response(status, [("Content-Type", content_type), ("Content-Length", str(len(raw))),
                                ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"),
                                ("Content-Security-Policy", "default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")])
        return [raw]
