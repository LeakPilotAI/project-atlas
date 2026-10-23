from concurrent.futures import ThreadPoolExecutor

import pytest
from app.services.paper_fixture_authority import pinned_fixture_reporter
from test_bound_daily_report import setup
from test_durable_partial_shutdown import fixture
from test_report_inventory import inventory


@pytest.mark.parametrize("field", ["identity", "version", "sources"])
def test_caller_cannot_replace_captured_pin(tmp_path, field):
    path, _ = fixture(tmp_path)
    setup(path)
    request = inventory(path)
    publish = pinned_fixture_reporter(request)
    if field == "sources":
        request[field]["positions"] = "changed"
    else:
        request[field] = "changed"
    with pytest.raises(ValueError):
        publish(path, day="1970-01-01", timezone="UTC", currency="USD", inventory=request)


def test_concurrent_report_retry_uses_one_revision(tmp_path):
    path, _ = fixture(tmp_path)
    setup(path)
    request = inventory(path)
    publish = pinned_fixture_reporter(request)
    def attempt(_):
        return publish(path, day="1970-01-01", timezone="UTC", currency="USD", inventory=request)
    with ThreadPoolExecutor(2) as pool:
        rows = list(pool.map(attempt, range(2)))
    assert rows[0] == rows[1]
    assert rows[0]["status"] == "INCOMPLETE"
