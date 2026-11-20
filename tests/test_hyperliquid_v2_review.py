import json
import sqlite3

import pytest
from app.services.hyperliquid_partial_fixture import (
    _body,
    _digest,
    publish_partial_daily_fixture,
)
from app.services.paper_writer_fixture import (
    close_fixture_writers,
    provision_fixture_writers,
    run_fixture_writer,
)
from test_hyperliquid_partial_fixture import append, fixture, request, view


@pytest.mark.parametrize("damage", ["stale", "schema", "boolean-revision", "duplicate-json"])
def test_replay_revalidates_semantics_not_merely_recomputed_local_hash(tmp_path, damage):
    f = fixture(tmp_path)
    append(f, request(f))
    with sqlite3.connect(f[0]) as db:
        body, raw = db.execute("SELECT body,event FROM operations").fetchone()
        event = json.loads(raw)
        r = event["request"]
        if damage == "stale": r["quote"]["observed_at"] -= 31
        if damage == "schema": r["schema"] = "UNKNOWN"
        if damage == "boolean-revision": r["expected_revision"] = False
        event["digest"] = _digest({k: v for k, v in event.items() if k != "digest"})
        body = _body(r)
        if damage == "duplicate-json": body = '{"schema":"UNKNOWN",' + body[1:]
        db.execute("UPDATE operations SET body=?,event=?", (body, _body(event)))
    with pytest.raises(ValueError): view(f)


@pytest.mark.parametrize("unacknowledged", [False, True])
def test_disposable_native_contract_bridge_requires_writer_drain_and_v2_ack(tmp_path, unacknowledged):
    f = fixture(tmp_path)
    r = request(f, quantity="0.5", price="104")
    roster = {"selected-perp": "fixture-incarnation-1"}
    provision_fixture_writers(f[1], roster)

    def mutation():
        def fault(phase):
            if unacknowledged and phase == "before_ack":
                raise OSError("fixture missing acknowledgement")
        append(f, r, fault=fault)

    kwargs = {"writer": "selected-perp", "incarnation": "fixture-incarnation-1", "operation": "exit-operation",
              "payload": _digest(r), "mutation": mutation}
    if unacknowledged:
        with pytest.raises(OSError): run_fixture_writer(f[1], **kwargs)
        with pytest.raises(ValueError): run_fixture_writer(f[1], **kwargs)
    else:
        run_fixture_writer(f[1], **kwargs)
        run_fixture_writer(f[1], **kwargs)  # Outer acknowledgement suppresses duplicate callback.
    drained = close_fixture_writers(f[1], roster)
    assert drained["status"] == ("INCOMPLETE" if unacknowledged else "DRAINED_FIXTURE_ONLY")
    calls = []
    with pytest.raises(ValueError):
        run_fixture_writer(f[1], **{**kwargs, "operation": "late-operation", "mutation": lambda: calls.append(True)})
    assert not calls
    options = {"expected_baseline": f[2], "day": "2026-10-23", "timezone": "UTC", "currency": "USD"}
    if unacknowledged:
        with pytest.raises(ValueError): publish_partial_daily_fixture(f[0], f[1], **options)
    else:
        receipt = publish_partial_daily_fixture(f[0], f[1], **options)
        assert not receipt["shutdown_authorized"] and receipt["revision"] == 1
    assert len(f[3].PaperJournal().list_open()) == 1 and f[4].load()["plans"][0]["status"] == "ENTERED"
