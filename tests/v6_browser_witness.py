"""Validate actual browser-driver observations; never fabricate a signoff."""

from urllib.parse import urlsplit

from scripts.observation_runtime.installed_acceptance_handoff import validate_ticket


def verify_window_continuity(expected_window, observations):
    """Reject a lost/replaced browser target; this never grants process ownership."""
    if (
        type(expected_window) is not dict
        or expected_window.get("app") != "Chrome"
        or type(expected_window.get("id")) is not int
        or expected_window["id"] <= 0
    ):
        raise ValueError("EXACT_RETURNED_CHROME_WINDOW_REQUIRED")
    stages = ("initial", "navigation_focus", "navigated", "rendered", "tab_closed")
    if type(observations) is not list or len(observations) != len(stages):
        raise ValueError("COMPLETE_BROWSER_LIFECYCLE_REQUIRED")
    last = -1
    for stage, observation in zip(stages, observations, strict=True):
        if (
            type(observation) is not dict
            or observation.get("stage") != stage
            or observation.get("error") is not None
            or observation.get("operator_stopped") is not False
        ):
            raise ValueError("BROWSER_FAILURE_OR_OPERATOR_STOP_NO_RETRY")
        window = observation.get("window")
        if (
            type(window) is not dict
            or type(window.get("id")) is not int
            or window.get("id") != expected_window["id"]
            or window.get("app") != expected_window["app"]
        ):
            raise ValueError("BROWSER_WINDOW_LOST_OR_REPLACED")
        if not observation.get("address_value") or not observation.get("document_url"):
            raise ValueError("CURRENT_BROWSER_URL_REQUIRED")
        when = observation.get("observed_ns")
        if type(when) is not int or when <= last:
            raise ValueError("BROWSER_OBSERVATION_ORDER_REQUIRED")
        last = when
    return True


def verify_disposable_browser_witness(
    ticket, *, address_value, document_url, body, test_tab_closed
):
    validate_ticket(ticket)
    if ticket["domain"] != "DISPOSABLE":
        raise ValueError("DISPOSABLE_BROWSER_WITNESS_ONLY")
    if (
        not isinstance(address_value, str)
        or not address_value
        or not isinstance(document_url, str)
        or not document_url
    ):
        raise ValueError("NATIVE_BROWSER_URL_EVIDENCE_REQUIRED")
    expected = urlsplit(ticket["url"])

    def origin(value):
        url = urlsplit(value)
        return (
            url.scheme,
            url.hostname,
            url.port,
            url.path.rstrip("/"),
            url.query,
            url.fragment,
            url.username,
            url.password,
        )

    address = address_value if "://" in address_value else "http://" + address_value
    if (
        origin(address) != origin(ticket["url"])
        or origin(document_url) != origin(ticket["url"])
        or expected.hostname != "127.0.0.1"
    ):
        raise ValueError("BROWSER_ORIGIN_OR_PORT_MISMATCH")
    required = (
        "ATLAS HARNESS V3 DISPOSABLE FIXTURE",
        f"Cycle {ticket['cycle']}",
        ticket["host_id"],
        "Selected PAPER account: UNAVAILABLE",
        "NO PROVIDERS. NO TRADING.",
        "synthetic test evidence",
    )
    if not isinstance(body, str) or not all(part in body for part in required):
        raise ValueError("ACTUAL_RENDERED_FIXTURE_IDENTITY_REQUIRED")
    if test_tab_closed is not True:
        raise ValueError("TEST_TAB_CLOSURE_REQUIRED")
    return {
        "ready_image_verified": True,
        "dashboard_rendered": True,
        "financial_unavailable": True,
        "test_tab_closed": True,
    }
