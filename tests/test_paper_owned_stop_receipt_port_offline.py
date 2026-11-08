"""Owner-side durable Stop receipt test doubles; zero runtime and provider access."""
from copy import deepcopy
from threading import Lock
from types import SimpleNamespace

import pytest

from app.services.unified_paper_runtime import UnifiedControlStopBridge


def receipt():
    return {"schema": "QD_CONTROL_STOP_V1", "phase": "FINISHED", "outcome": {
        "schema": "QD_AUTO_SHUTDOWN_V1", "mode": "SHUTDOWN_FLATTEN",
        "status": "FLATTENED", "position_state": "FLAT",
        "process_shutdown": "VERIFIED_EXIT",
        "lanes": {"QUALITY_DIPS": {"state": "ACKNOWLEDGED_FLAT_AND_DRAINED"},
                  "HYPERLIQUID": {"state": "ACKNOWLEDGED_FLAT_AND_DRAINED"}},
    }}


class MockDurableLedger:
    def __init__(self, row):
        self.row = row
        self.calls = 0

    def reserve_existing(self, session, mode):
        assert session == "offline-unified-session" and mode == "SHUTDOWN_FLATTEN"
        self.calls += 1
        if self.row == "RAISE":
            raise OSError("offline simulated ledger inaccessible")
        return deepcopy(self.row)


def bridge(row=None, *, persisted=True):
    r = receipt()
    b = object.__new__(UnifiedControlStopBridge)
    b.stop_lock = Lock()
    b.progress = deepcopy(r)
    b.stop_ledger = MockDurableLedger(row if row is not None else {"state": "FINISHED", "receipt": r})
    b._receipt_persisted = persisted
    b.runtime = SimpleNamespace(grant={"session_id": "offline-unified-session"})
    return b


def test_owner_reads_exact_durable_two_lane_receipt():
    b = bridge()
    assert b.verify_durable_stop_receipt("SHUTDOWN_FLATTEN", receipt()) is True
    assert b.stop_ledger.calls == 1


@pytest.mark.parametrize("mutate", [
    lambda r: r["outcome"]["lanes"].pop("HYPERLIQUID"),
    lambda r: r["outcome"]["lanes"]["QUALITY_DIPS"].update(state="OPEN"),
    lambda r: r["outcome"].update(status="SHUTDOWN_INCOMPLETE"),
    lambda r: r["outcome"].update(process_shutdown="UNVERIFIED"),
    lambda r: r.update(phase="IN_PROGRESS"),
])
def test_no_paper_result_claimed_flat_from_modified_memory_receipt(mutate):
    b = bridge()
    r = receipt()
    mutate(r)
    assert not b.verify_durable_stop_receipt("SHUTDOWN_FLATTEN", r)
    assert b.stop_ledger.calls == 0


@pytest.mark.parametrize("state", ["PENDING", "MISSING", "RAISE"])
def test_pending_or_corrupt_durable_readback_refuses(state):
    row = "RAISE" if state == "RAISE" else {"state": state, "receipt": receipt()}
    b = bridge(row)
    assert not b.verify_durable_stop_receipt("SHUTDOWN_FLATTEN", receipt())
    assert b.stop_ledger.calls == 1


def test_no_in_memory_receipt_is_enough_without_persisted_ack():
    b = bridge(persisted=False)
    assert b.verify_durable_stop_receipt("SHUTDOWN_FLATTEN", receipt()) is False
    assert b.stop_ledger.calls == 0


def test_modified_stored_receipt_refused_even_when_both_lanes_flat():
    r = receipt()
    r["outcome"]["cash"] = "forged"
    b = bridge({"state": "FINISHED", "receipt": r})
    assert not b.verify_durable_stop_receipt("SHUTDOWN_FLATTEN", receipt())
    assert b.stop_ledger.calls == 1


def test_incorrect_mode_or_missing_owner_refused():
    b = bridge()
    assert not b.verify_durable_stop_receipt("EMERGENCY", receipt())
    b.runtime.grant = {}
    assert not b.verify_durable_stop_receipt("SHUTDOWN_FLATTEN", receipt())
    assert b.stop_ledger.calls == 0
