"""Harness-pinned verifier; fixture authority is not production authority."""
from copy import deepcopy

from app.services.paper_bound_daily_report import publish_inventory_bound_fixture


def pinned_fixture_reporter(expected):
    """Capture a complete harness receipt before accepting untrusted requests.

    The harness is the trust boundary. This function cannot establish external
    independence, prevent whole-machine rollback, or authorize production.
    """
    if (type(expected) is not dict or set(expected) != {"identity", "version", "sources"}
            or type(expected["identity"]) is not str or not expected["identity"]
            or type(expected["version"]) is not int or expected["version"] < 1):
        raise ValueError("Complete harness pin required")
    pin = deepcopy(expected)

    def publish(path, *, day, timezone, currency, inventory):
        if inventory != pin:
            raise ValueError("Request differs from fixed harness source pin")
        return publish_inventory_bound_fixture(path, day=day, timezone=timezone, currency=currency,
                                               inventory=deepcopy(pin), expected_identity=pin["identity"],
                                               expected_version=pin["version"])
    return publish
