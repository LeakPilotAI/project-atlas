"""R7E47AC: isolated HTTP sender.

No automatic invocation. Live authorization remains disabled.
"""

import json
import urllib.error
import urllib.request

from scripts.observation_runtime.r7e47aa_transport import (
    MAX_RESPONSE_BYTES,
    TransportRefused,
)

ENDPOINT = "https://api.hyperliquid.xyz/info"
BODY = {"type": "metaAndAssetCtxs"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def build_request():
    return urllib.request.Request(
        ENDPOINT,
        data=json.dumps(BODY).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )


def describe_request():
    request = build_request()
    return {
        "url": request.full_url,
        "method": request.get_method(),
        "body": json.loads(request.data),
        "max_response_bytes": MAX_RESPONSE_BYTES,
        "timeout_seconds": 10,
        "redirects": False,
        "automatic_retries": False,
        "network_executed": False,
    }


def send_once():
    """Not authorized for invocation until external controls are verified."""
    raise TransportRefused(
        "Network execution disabled pending provider authorization"
    )


def _http_send_once():
    """Unconnected implementation; do not invoke without authorization."""
    request = build_request()
    opener = urllib.request.build_opener(
        NoRedirect(),
        urllib.request.ProxyHandler({}),
    )

    try:
        with opener.open(request, timeout=10) as response:
            if response.status != 200:
                raise TransportRefused("Unexpected HTTP status")

            raw = response.read(MAX_RESPONSE_BYTES + 1)

            if len(raw) > MAX_RESPONSE_BYTES:
                raise TransportRefused("Response too large")

            return raw

    except (urllib.error.URLError, TimeoutError) as error:
        raise TransportRefused("HTTP request failed") from error
